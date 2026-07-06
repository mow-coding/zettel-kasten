# Changelog

All notable public releases of `zettel-kasten`, `zet`, and `ZET` should be documented here.

This project uses semantic versioning for public compatibility checkpoints.

## Unreleased

## v0.3.187 - 2026-07-07

AI artifact lifecycle inventory checkpoint. Additive; no migration.

- **AI artifact inventory.** Added read-only `archive ai-artifact-inventory --dry-run`
  (aliases `ai-artifact-status`, `ai-residue-inventory`) for bounded inventories of
  AI-generated working files and chat logs under `.wom-scratch/`,
  `workbench/ai-scratch/`, `staging/ai/inbox/`, and `staging/ai/reviewed/`.
- **Fate-oriented status board.** The inventory reports `unreviewed_ai_artifact` versus
  `source_intake_recorded` candidates, artifact kinds such as `ai_chat_log_jsonl`,
  and safe next fates: preserve raw bytes as an objet, register derived text, distill
  to a draft zet, link to an existing zet, defer review, or discard with receipt evidence.
- **Privacy boundary.** The command reads no file bodies, calculates no content hashes,
  writes nothing, deletes nothing, creates no zets, calls no providers, and hides
  archive-relative paths unless `--show-relative-paths` is explicitly used for local
  operator review.

## v0.3.186 - 2026-07-07

Basoon v0.3.185 revalidation follow-up for read-only adopt diagnostics and the next doctor mint-receipt progress gap. Additive; no migration.

- **Adopt stop-after-plan diagnostic mode.** `object-storage-adopt-existing` now accepts
  `--stop-after-plan`, so an operator can reuse an `--approve` command shape, resolve the
  key-map/resume summaries, and stop before credential value reads, provider HEADs, manifest
  updates, or execution receipt writes. The final JSON/text result stays on stdout; optional
  progress stays on stderr.
- **Same-store `wom_uploaded` gating diagnostics.** Adopt summaries now distinguish raw
  same-`store_ref` `wom_uploaded` location counts from the stricter skip candidates that match
  this run's content-addressed key hint, resolved `remote_key`, and digest binding. This explains
  why a simple manifest count can be higher than the matching resume skip count.
- **Doctor mint-receipt continuation progress.** `doctor --strict --progress` now emits detailed
  mint-receipt sub-steps for the first three receipts and records `completed receipt checks`, so a
  stall after `target mint receipt link ok` is distinguishable from a slow next receipt.

## v0.3.185 - 2026-07-06

Basoon v0.3.183 revalidation follow-up for adopt resume diagnostics, doctor mint-link progress, and version import-origin warnings. Additive; no migration.

- **Same-provider nonmatching adopt diagnostics.** `object-storage-adopt-existing --progress` now
  reports a second resume diagnostic when digest-bound same-provider object-storage locations exist
  but do not match this run's `store_ref` or resolved `remote_key`. The JSON summary includes
  nonmatching location counts split by availability plus store-ref/key mismatch counts, and
  `provider_location_mismatch_gap` explains why legacy declared rows are not resume-skip candidates.
- **Doctor mint-link sub-steps.** `doctor --strict --progress` now splits `checking target mint
  receipt link` into target mint block read, block validation, receipt-path read, relative-path
  formatting, comparison, and ok/error recording. This narrows the next large-archive stall point.
- **Version import-origin warning.** `archive version <root>` text output now identifies whether the
  imported module path is redacted and points operators to `--no-redact-local-paths`; mismatch
  warnings now explain that the active `archive` command may be importing a different WOM-kit module
  than the project-local source mirror.

## v0.3.184 - 2026-07-06

Human document view for canonical zet frontmatter. Additive; no migration.

- **Document read mode.** `archive read-zettel --section document` now returns the zet body with
  frontmatter details hidden, and text output prints only the document body. This gives operators
  and AI runtimes a clear WOM-rendered reading surface distinct from raw Markdown files.
- **Viewer contract flags.** `read-zettel` output now marks `viewer_mode`, `frontmatter_hidden`,
  and `raw_frontmatter_delimiters_echoed: false` so caller UIs can distinguish metadata panels from
  document content without guessing.
- **Frontmatter viewer guidance.** New public docs clarify that YAML frontmatter remains part of the
  canonical storage format, while human-facing viewers should hide it by default or show it in a
  folded metadata panel. `ai-response-concept-guide` exposes the same rule for AI runtimes.

## v0.3.183 - 2026-07-06

Adopt resume-gap diagnostics and deeper doctor frontmatter progress. Additive; no migration.

- **Adopt resume state counts.** `object-storage-adopt-existing` now counts matching existing
  provider/store/key manifest locations by availability: total, `wom_uploaded`,
  `declared_uploaded`, and other. `--progress` emits a content-free `adopt-plan` resume summary
  before the verified HEAD loop starts.
- **Declared-upload gap warning.** If matching `declared_uploaded` locations exist, adopt emits
  `declared_upload_resume_gap` to explain why `--skip-existing-wom-uploaded` cannot skip them:
  they are not WOM-verified and still need verified adopt HEADs before promotion to
  `wom_uploaded`.
- **Doctor frontmatter sub-steps.** `doctor --progress` now breaks target frontmatter loading into
  text read, BOM check, frontmatter fence parse, YAML load, loaded/cache-hit, target BOM cache, and
  mint-link checks.

## v0.3.182 - 2026-07-06

Basoon v0.3.180 revalidation follow-up for adopt resume and doctor receipt progress. Additive; no
migration.

- **`object-storage-adopt-existing --skip-existing-wom-uploaded`.** Verified adopt now has an
  explicit resume helper: when a matching `wom_uploaded` manifest location already exists for the
  same provider/store/key, the command can skip the remote HEAD for that object and report
  `already_wom_uploaded_manifest`. The default still re-HEADs, and the option is refused with
  `--content-hash-verify`.
- **Resume visibility.** Adopt planning now counts matching existing `wom_uploaded` locations and
  emits a `resume_hint` warning when they exist but the resume skip option is not enabled.
- **Doctor `mint-receipts` sub-step progress.** `doctor --progress` now shows internal
  `mint-receipts` sub-steps for the sampled receipt positions and prints a cache summary for file
  SHA-256, zettel frontmatter, and BOM evidence.

## v0.3.181 - 2026-07-06

Staged cleanup operator progress. Additive; no migration.

- **`archive staged-cleanup-check --progress`.** The report-only cleanup verifier can now
  stream content-free stage progress to stderr while it loads object records, scans zettel
  references, walks staged entries, verifies files, and hashes large source/store files.
- **Large-file liveness.** `sha256_path` gained an optional progress callback; existing callers
  keep the same digest behavior, while staged cleanup uses it only for large-file hash progress.
- **Regression tests.** Added coverage for content-free staged-cleanup progress, CLI progress
  output, and digest-preserving hash progress callbacks.

## v0.3.180 - 2026-07-06

Large-archive performance hardening for adopt planning and doctor receipt checks. Additive; no
migration.

- **`object-storage-adopt-existing` adopt-plan manifest index.** Large key-map adopts now build
  one per-run `objects/manifests/files.jsonl` object-id index before plan resolution instead of
  repeatedly scanning the manifest for every object. This targets the v0.3.179 basoon
  revalidation bottleneck where `adopt-plan` itself was slow before provider HEAD checks began.
- **Doctor per-run file caches.** `archive doctor` now reuses file SHA-256 and zettel
  frontmatter/BOM evidence within one run, reducing repeated work in receipt stages such as
  `mint-receipts` without changing diagnostics.
- **Regression tests.** Added tests that fail if adopt planning falls back to per-object
  `find_manifest_record` scans, if doctor hashes the same receipt ref twice in one run, or if
  cached zettel frontmatter is not reused.

## v0.3.179 - 2026-07-06

Redacted remint-reconcile diagnostic output. Additive; default output is unchanged.

- **`archive remint-reconcile --diagnostic-only --format json`.** A dry-run can now return a
  redacted diagnostic projection with drift class, body-change status, `body_diff_diagnostic`,
  and frontmatter field names/counts while omitting `current_canonical_text` and
  `frontmatter_field_changes` values. This lets operators inspect the v0.3.176 body-diff
  numbers without dumping canonical body text into a JSON transcript.
- **Approve remains review-visible.** `--diagnostic-only` is refused with `--approve` because
  approval must still show the current on-disk content for human review.

## v0.3.178 - 2026-07-06

Operator progress output for long archive checks and large object-storage adopts. Additive; no
migration.

- **`archive doctor --progress`.** Doctor already had internal stage progress plumbing; the CLI
  now exposes it. A long `doctor --strict` run can stream `[doctor] <stage>: start/done` lines
  to stderr, so an operator can tell which validation stage is active without changing JSON or
  text diagnostic output.
- **`object-storage-adopt-existing --progress`.** Large verified adopt/key-map batches now have
  optional progress callbacks for plan resolution, declared adopt, and verified remote-HEAD
  loops. CLI progress streams safe stage/count heartbeats to stderr with no object ids,
  remote keys, bucket names, provider URLs, exact credential refs, tokens, or secret values.
  Reporting is throttled to the first item, every 100th item, and the last item per loop.

## v0.3.177 - 2026-07-06

Force-reupload ledger-only hardening for the object-storage upload adapter. Additive; no
migration; default behavior is unchanged.

- **`--force-reupload` now outranks the resume ledger even when the manifest is not
  `already_uploaded`.** A post-crash or handoff state can leave a terminal
  `resume-ledger` row while the manifest no longer has a `wom_uploaded` location. In that
  state, v0.3.176 could still return `skipped_already_present` with 0 provider PUTs even
  though the operator requested `--force-reupload`. v0.3.177 passes the force decision into
  the executor for that ledger-only state, so a reviewed force run reaches the provider PUT
  path (including forced small multipart) after the same pre-PUT
  `sha256(local)==object_id` check.
- **Zero-PUT force attempts fail closed.** Force runs now mark per-object execution output
  with `forced_reupload: true`; if no provider PUT call is attempted, the run reports
  `force_reupload_not_performed` and `ok:false` instead of a misleading success. Existing
  default skip/idempotency behavior is unchanged when the flag is absent.

## v0.3.176 - 2026-07-06

A content-free reconcile body-diff diagnostic (DX-only). Additive; **no classification or
behavior change, no migration.** The classifier — `bytes_normalized_for_content_compare`, the
Tier A/B anchor logic, the drift_class predicate, `classification_basis`, and
`content_change_ack_required` — is byte-identical with and without this change.

- **Content-free `body_diff_diagnostic` on the reconcile plans.** When
  `archive remint-reconcile` (and the sibling `archive retire-draft-reconcile`) classifies a
  drift as `content_change` because the two bodies still differ AFTER the single leading
  BOM strip + CRLF/CR→LF fold, the plan now carries a `body_diff_diagnostic` decoration so a
  client running `--strip-bom --dry-run` can self-diagnose WHICH kind of sub-BOM residual they
  have without echoing any body bytes. It reports ONLY non-content facts: a fixed `category`
  label (`final_newline_only`, `trailing_whitespace_only`, `unicode_normalization_only`, or
  `content_difference`), a `first_differing_byte_offset` (an integer index into the normalized
  form), a `normalized_length_delta` (an integer byte delta), and — for the unicode case only —
  a closed-enum NFC/NFD `canonical_form`/`snapshot_form` label. A non-`content_difference`
  category is reported ONLY when its transform makes the two normalized bodies EQUAL TO EACH
  OTHER (mutual full reconciliation), so a mix of whitespace/normalization drift AND a real
  content edit is never laundered to a benign label — it stays the honest `content_difference`.
  It is a **STRICT CLASSIFICATION NO-OP**: it is computed AFTER the drift_class predicate and
  only added to the output dict, exactly like the existing strip-BOM preview, and never
  influences `drift_class` / `classification_basis` / `content_change_ack_required`. It emits
  only integers and fixed labels — never a body substring, slice, or repr. The key is ABSENT
  when there is no snapshot anchor (Tier C, `body_changed` None) or when the bodies are
  identical (`format_drift`, `body_changed` False), so it never shows a misleading residual.
  Both CLI text printers gain one content-free summary line; JSON consumers see the new key
  only when it is present. Additive; no migration.

## v0.3.175 - 2026-07-05

Live-verification aids for the object-storage upload adapter (Stage 2): a forced re-upload of
an already-present object, and multipart-proven upload tier2. Additive; no migration; default
behavior and existing receipts/manifests are byte-identical.

- **Approval-gated `--force-reupload`.** `object-storage-upload --force-reupload` RE-PUTs an
  already-present object whose remote bytes already size/hash-match, so a client can exercise
  a LIVE provider PUT (e.g. a forced small multipart) on the only object it has. It requires
  `--approve` AND `--reviewed-by` (a deliberate provider PUT cost and a live overwrite), is
  inert under `--dry-run`, and is REFUSED for any non-sha-derived `--key-strategy` (the
  conflict-guard bypass is safe only when the remote key embeds the object digest). The
  pre-PUT local `sha256(local)==object_id` re-verify still runs, so a corrupt local file is
  refused before any PUT; the HEAD-after GET-rehash verification, orphan cleanup on mismatch,
  and the cumulative `OBJECT_STORAGE_TOTAL_PUT_CEILING` all remain in force. The execution
  receipt records a top-level `forced_reupload` boolean. Default (flag absent) is
  byte-identical to prior behavior.
- **Multipart-proven upload tier2.** `object_storage_proven_tier` now recognizes a real
  multipart execution (`part_count > 1` on an `uploaded` receipt) as a legitimate tier2 proof,
  in addition to the existing 5 GiB `bytes_uploaded` path (kept verbatim). A forced small
  multipart — already possible via `--multipart-part-size`/`--allow-tiny-parts` — is now the
  tier2 proof it actually is, so a byte-external client with no >5 GiB object can prove upload
  tier2. The `status == "uploaded"` guard blocks a fabricated skip receipt from minting tier2.
  The adopt tier ladder (`object_storage_adopt_requested_tier` / `object_storage_adopt_proven_tier`)
  is unaffected. Additive; no migration.

## v0.3.174 - 2026-07-05

Decouple verified-adopt tiered gating from the object-storage-upload 5 GiB multipart proof.
Additive; no migration; existing receipts and manifests are unaffected.

- **Adopt gate decoupled from the upload tier ladder.** A verified adopt is HEAD-only (it
  moves zero bytes and runs a per-object HEAD-verify self-limit), so gating it on the
  object-storage-upload 5 GiB / multipart tier proof was wrong: it deadlocked a large
  first-live batch handover that has no large-object PUT to prove. `object-storage-adopt-existing`
  now uses a binary adopt-specific gate — one prior verified tiny-first adopt unlocks a batch
  adopt of any size. New pure functions `object_storage_adopt_requested_tier` /
  `object_storage_adopt_proven_tier` carry the adopt rule; the upload tier ladder
  (`object_storage_requested_tier` / `object_storage_proven_tier`) is byte-identical and the
  upload gate keeps `tiered_gate_unmet`. The adopt blocker token is renamed
  `tiered_gate_unmet` → `adopt_tiny_first_unmet`. The adopt proof is derived only from
  execution receipts carrying a verified `adopt_verification` marker, so an upload receipt
  (including an upload that skipped on already-matching bytes) never unblocks adopt, a
  declared/unverified adopt never counts, and a wrong `--key-map` still self-limits to zero
  adopts. Additive; no migration.

## v0.3.173 - 2026-07-05

One additive command. It needs no migration and leaves every default path byte-identical
to v0.3.172.

- **Archive base link type sync.** New `archive migrate --target base-link-types
  --dry-run|--approve --reviewed-by <actor>` pulls every base WOM-kit link type that is
  missing from a stale archive-local `zettel-kasten/types.yml` into that file. It is
  append-only and no-clobber: missing base entries are deep-copied verbatim and appended
  after the archive's existing entries; no existing entry is removed, renamed, reordered,
  or altered in value, so an archive's divergent same-id customization always wins (it is
  reported under `present_not_overwritten`). Its id set is a strict superset of the
  recommended-9 `link-types-v0.3` migration set — it also covers `continues` (added to the
  base in v0.3.168) and any other base-only id. `--reviewed-by` is required with
  `--approve`. It writes a receipt (`receipt_kind: base_link_types_sync`) under
  `receipts/migrations/base-link-types.*.migration.json`, is atomic with rollback, and is
  idempotent (a second run with nothing missing is a clean no-op — no receipt, no blocker).
  There is deliberately **no `--revert`** (`--revert --target base-link-types` fails
  closed).
- **No-`types.yml` safe branch.** If the archive has no local `zettel-kasten/types.yml`,
  sync writes nothing and creates no file: the archive already inherits all current and
  future base link types via the base fallback, and creating a local `types.yml` would
  permanently shadow (freeze) that inheritance.
- **Discoverability.** `archive doctor` now routes an operator hitting an undefined edge
  type toward `archive migrate --target base-link-types --dry-run`.

Honesty facts, stated plainly:

1. Once an archive has its **own** `zettel-kasten/types.yml`, it shadows the base
   permanently — every future base link type also needs a manual `migrate --target
   base-link-types`. There is no automatic propagation.
2. Sync copies base entry shapes **as of this release** (a snapshot, not a live link).
3. Sync normalizes/rewrites the whole `types.yml` via `safe_dump` (comments, anchors,
   flow-style, and key ordering may be normalized) — exactly like the sibling
   `link-types-v0.3` migration. Existing link-type entries are preserved by value/id;
   surrounding formatting is not byte-preserved. Review the diff.

## v0.3.172 - 2026-07-05

Two verification-honesty fixes. Both are additive, need no migration, and leave every
default path byte-identical to v0.3.171.

- **Live-multipart part-size override.** New `--multipart-part-size <BYTES>` and
  `--allow-tiny-parts` on `object-storage-upload`. Default part size (64 MiB) is
  unchanged; an override is bounded to `[4096, 64 MiB]` and below the default requires
  `--allow-tiny-parts`. It lets an operator FORCE multipart on a small object (paired
  with a lowered `--multipart-threshold`) to prove LIVE R2 multipart — real per-part
  SigV4 and an R2-accepted `CompleteMultipartUpload`. It changes ONLY `handle.read()`
  fragmentation: the whole-object before-hash, the full-object sha256 handed to
  `complete_multipart`, the HEAD-after full-object verify, SA-5 delete-on-mismatch, and
  the leak gate are all invariant. On any violation the run does not proceed and
  `put_calls` stays 0. Honest framing corrected: the multipart CODE path was already
  fake-transport unit-tested; what these flags let an operator prove is the LIVE path.
  Real R2 rejects multipart parts < 5 MiB except the last, so a tiny part is a
  fake-transport/local aid and a live tiny-part rejection is an upload rejection, never a
  silent bypass.
- **Threshold-floor re-basing.** When a part size is supplied, the `--multipart-threshold`
  floor is compared against the effective part size (not the 64 MiB constant), so the
  threshold can drop below 64 MiB together with the part size — otherwise the small-object
  multipart path was dead on arrival.
- **Receipt field.** The execution receipt gains `effective_multipart_part_size_bytes`
  (additive; the schema has no `additionalProperties:false` and does not list it in
  `required`). It lets an auditor verify `ceil(size/part_size) == part_count`.
- **Strip-bom dry-run parity (both reconcile surfaces).** `--strip-bom` on a dry-run of
  `remint-reconcile` AND `retire-draft-reconcile` now previews the same strip-intent
  metadata (`bom_stripped`, `bom_strip_note`) an `--approve` run records. The classifier
  is already BOM-insensitive, so this is a strict classification NO-OP: `drift_class` and
  `content_change_ack_required` are identical whether `--strip-bom` is passed or not, and
  a real `content_change` is never laundered to `format_drift`.

## v0.3.171 - 2026-07-04

`object-storage-adopt-existing --key-map`: the hardened 158 GB false-skip fix. A
new opt-in flag lets an operator hand WOM the EXACT existing remote key per object
(JSONL: `{"sha256":"<64hex>","remote_key":"<key>"}` per line), so objects a client
already uploaded under their own per-object extension are adopted instead of being
re-uploaded. Additive and adopt-only; the default path (no `--key-map`) is
byte-identical to before, and no `object-storage-upload` behavior changes.

- New `--key-map` on `object-storage-adopt-existing` (adopt subcommand only). For a
  mapped object the map value becomes the resolved `remote_key` verbatim, bypassing
  the `object_storage_remote_key` template; `--key-strategy`/`--key-prefix`/
  `--key-append-extension` are IGNORED for mapped objects. This recovers the
  prehashed-ledger case where the manifest `logical_key` has no filename extension,
  so `--key-append-extension` recovers nothing and every template HEAD 404s.
- Binding audit `object_storage_map_key_binds_digest_segment`: an operator-supplied
  key must bind the object's 64-hex sha256 as a full `/`-delimited path segment OR
  the filename stem — strictly stronger than the shipped substring check. A map that
  points one object's sha at a different object's real key is refused (per-row skip,
  re-uploads). This narrows, but does not eliminate, the same-size-wrong-bytes hole;
  `--content-hash-verify` remains the only cryptographic proof (documented residual).
- Size is ALWAYS sourced from the manifest, never from the map; a mapped object whose
  manifest `size_bytes` is null never adopts on presence alone
  (`mapped_but_no_manifest_size_count`). A mapped key that 404s or size-mismatches
  re-uploads, never false-skips (live HEAD gate unchanged). Every written delta still
  passes the existing adopt leak guard and `safe_object_storage_remote_key`.
- Fail-safe map loader `read_object_storage_key_map` (fail-closed UTF-8/JSONL, BOM
  strip, 200,000-entry cap): an unreadable/non-JSONL file, a row missing a field, a
  non-hex sha, an unsafe key, a duplicate sha with conflicting keys, or an over-cap
  file is whole-run-fatal — adopt ZERO, no partial adopt. A duplicate sha with the
  identical key is deduped.
- Reporting: `adopt_summary` gains `key_map_used`, `mapped_count`, `unmapped_count`,
  `map_rejected_count`, and `mapped_but_no_manifest_size_count`; each `adopt_results`
  row carries `key_source` ∈ {`template`,`map`,`map_rejected`,`unmapped`}. A
  discoverability warning points at `--key-map` (and the lossy mime-derived fallback)
  when a template run with `--key-append-extension` recovers no extension for a high
  fraction of objects.

## v0.3.170 - 2026-07-04

Runtime AI-operator discipline. A normative "AI-Operator Discipline" section is
added to the operator-facing runtime surfaces, plus a complementary
source-substitution axis in the provenance model. Docs-only and additive; no
command, schema, receipt, or archive change, and no new WOM-enforced check.

- New normative `## AI-Operator Discipline` section on the runtime-visible
  surfaces — the three `AGENTS.md` templates (personal/company/family, identical
  block), the runtime `SKILL.md`, and `wom-ai-runtime-skill-plugin-layer.md` (with
  matching `Skill Template` mirror bullets) — stating three behavioral norms an
  operator AI applies: (a) PROVENANCE FIDELITY — record the source the human
  actually encountered (the exact video/edition/translation/language they saw);
  never silently substitute a "more authoritative"/original source; if a better
  source exists, ASK, and keep it as a SEPARATE ref, not a replacement; (b)
  ENUMERATE TOOLS BEFORE DECLARING IMPOSSIBLE — check installed/available tools
  (local CLIs, MCP servers, the derive-text tool-readiness surface) before saying a
  task cannot be done or degrading it, rather than concluding from one or two
  probes; (c) CARRY ESTABLISHED STATE — carry forward already set-up/approved state
  (session or `ops/operational-context.yml`) instead of re-asking as if first-time.
- `text-provenance-hierarchy.md` gains a new `## 7. Encountered-Source Fidelity
  (Source-Substitution Axis)` subsection that names both axes explicitly: the
  existing L0 derivation-tool axis (do not overwrite an object because a better
  parser/OCR/model appears) and the new source-substitution axis (do not replace
  the source the human actually encountered with a "more authoritative" one). The
  two are complementary; both preserve the provenance of the user's actual thought.
- One-line descriptive references from `ai-response-concept-guide.md` and
  `ai-response-contract.md` point to the discipline norms. These are guidance an
  operator AI applies; the commands validate nothing and enforce nothing. WOM does
  not validate provenance fidelity, tool enumeration, or state carry-over.

## v0.3.169 - 2026-07-04

Operator-feedback delivery ledger and batched mark-delivered. Both commands are
additive; no archive migration, no id rewrite, no hash change.

- Read-only `archive operator-feedback-ledger` (aliases `feedback-ledger`,
  `feedback-board`): enumerates `ops/feedback/*.yml` and aggregates delivery status
  as counts by draft/delivered/acknowledged/resolved/archived plus a pending
  (draft) list and the newest delivery-boundary timestamp among delivered records.
  It projects only feedback id + status + safe timestamps — it reads no feedback
  body and echoes no feedback ref, title, path, token, or secret values — and
  writes nothing. Malformed or non-mapping records are counted into an `unreadable`
  bucket and skipped so one bad file never fails the whole board. Honest boundary:
  `delivered_at` is stamped only by mark-delivered, so records delivered via the
  older `--status delivered` path have no `delivered_at` and the boundary falls back
  to their `updated_at`; it is not proof of external delivery.
- Approval-gated `archive operator-feedback-mark-delivered` (alias
  `feedback-mark-delivered`): in one batched action marks every pending `draft`
  record as `delivered`, stamps `delivered_at`, sets `reviewed_by`, and refreshes
  `updated_at`, so the operator no longer hand-edits each record. `--dry-run`
  previews which records would transition and writes nothing; `--approve` (requires
  a safe `--reviewed-by`) reads each record, preserves every other field verbatim,
  re-validates the mutated record against the shipped schema, writes the transitions
  atomically per record, and writes one
  `receipts/operator-feedback/delivery-batch.<ts>.<batch-digest>.json` receipt (the
  per-batch digest in the filename keeps two same-second batches from colliding).
  `--only <id>` marks a single record. It only transitions `draft->delivered`
  (never touching acknowledged/resolved/archived), is idempotent — a no-op re-run
  marks nothing new and writes no receipt — reports and skips malformed records
  without half-writing others, and reads no feedback body.
- Truth boundary: this is metadata lifecycle only. `external_submission_performed`
  stays `false`; `delivered` means the operator marked it delivered, not that
  anything was submitted externally or proven received.
- Schema additions (additive): `operator-feedback.schema.json` gains optional
  `delivered_at` / `acknowledged_at` string properties (not required), and a new
  `operator-feedback-delivery-receipt.schema.json` ships for the batch receipt.
- Closes the v0.3.149 "Still Future: feedback status board" item.

## v0.3.168 - 2026-07-04

Draft-time identity hygiene, honest human affirmation, and continuation edges.
All five items are additive; no archive migration, no id rewrite, no hash change.

- Draft-id hygiene, forward-only (Item 마): the empty-slug fallback token in
  `make_zettel_id` changes from `draft` to `note`, so a titleless or pure-Hangul
  title no longer yields a misleading `zet_<ts>_draft` id. The fix touches ONLY the
  generator of new draft ids — before any reference can exist — so no existing
  canonical id is renamed or normalized and mint gains no id-rewrite path. The
  existing same-second collision loop is unchanged (`…_note`, `…_note_2`).
- Attributed mint affirmation (Item 나): `mint-zet` gains a repeatable `--affirm`
  flag (accepts only the two human-review items `one_clear_purpose`,
  `sensitive_content_reviewed`) that requires `--reviewed-by`. An affirmation is
  threaded into the on-the-fly checklist evaluation (source label `cli_affirmation`,
  distinct from `mint_frontmatter`/`legacy_promotion_frontmatter`/`machine`) so the
  item evaluates as passed for this mint without a YAML hand-edit, and is recorded in
  a new attributed `affirmations` block in the mint receipt (`item_id`, `affirmed_by`,
  `affirmed_at`). `--affirm` is inert without an attributed reviewer (hard error),
  cannot override machine-enforced items, and never flips an explicit YAML `false`.
  Honest residual: like the pre-existing `--reviewed-by` gate, `--affirm` cannot
  prove the reviewer string names a real human; it adds no new self-affirm hole and
  its guarantee is auditability, not string-sniffing.
- No silent auto-delete; discoverability pointer only (Item 다): a successful mint
  result gains a `next_safe_actions` list pointing to
  `archive retire-draft --zettel-id <id> --dry-run`, printed in text mode. Mint still
  never deletes the consumed inbox draft; retirement stays its own approval-gated step.
- Base `continues` edge type (Item 라): a `continues` link type is added to the base
  vocabulary in both `types.yml` files (KIT and fake-archive fixture), carved away
  from `derived_from`, `references`, `derived`, `supersedes`, and a generic `sequence`
  step. It is deliberately NOT added to `CONNECTION_IMPORT_RECOMMENDED_EDGE_TYPES`, so
  migration/revert and every pinned link-type test stay green untouched. Trade-off:
  archives that vendored their own `types.yml` add the entry manually (it is additive).
- Draft-time `--kind` validation (Item 가): `create-draft` now validates `--kind`
  against the archive's own `zettel-rules.yml` and emits a WARNING (not a block) that
  lists the valid kinds; default stays `fleeting_capture`, no argparse `choices=`. The
  warning is now printed in the non-dry-run text path too, and a read-only
  `--list-kinds` flag lists the archive's valid note kinds and exits without writing.

## v0.3.167 - 2026-07-04

- Snapshot-drift-aware `format_drift` classification for `remint-reconcile` (Item 1):
  a new `normalized_content_match` anchor tier grants `format_drift` even when the
  draft snapshot itself drifted, but ONLY behind two independent proofs sourced from
  un-tampered inputs — normalized body identity AND a snapshot raw-vs-normalized
  delta that is provably newline/BOM-only — plus an EMPTY frontmatter diff. Because
  the drifted snapshot is not sha-anchored, that frontmatter diff is the union of a
  full-field reconstruction over EVERY content field (`visibility`, `kind`, `facets`,
  `provenance`, `edges`, `created_at`, `source_refs`, …) AND an `id`/`title`
  cross-check against the **mint receipt**. This closes the tampered-snapshot hole in
  full: a canonical edit to any content field — not just `id`/`title` — falls to
  `content_change`, and a snapshot whose frontmatter was tampered to match a tampered
  canonical is caught by the receipt cross-check. A new `classification_basis`
  field records why a `format_drift` was granted. The prime directive is unchanged:
  any uncertainty falls to `content_change` and requires `--content-changed-ack`.
- New `retire-draft-reconcile` sibling command (Item 2): honestly reconciles a
  retire-draft receipt's four refs (source/target/mint_receipt/snapshot) after
  newline/BOM or content drift, inheriting the Item 1 discipline (a target/snapshot
  ref is `format_drift` only when the shared mint-reconcile classifier proves the
  canonical and snapshot content-identical; the `mint_receipt` pointer ref is
  raw-sha only). The doctor now attaches a `suggested_command` route to the
  previously-bare `mint_retired_draft_sha_mismatch` finding. New sibling audit
  receipts live under `receipts/mint/retired-draft-reconciles/`, and the retire
  receipt gains an append-only `reconcile` provenance block.
- New opt-in `--strip-bom` flag on both reconcile commands (Item 3): removes exactly
  the 3-byte leading UTF-8 BOM (`format_drift` by definition). No-op refusal when no
  BOM is present, a content-preserving invariant asserted before an atomic rewrite,
  and — the load-bearing guarantee — it NEVER bypasses the content-change ack gate.
- `live_execution_allowed_now` honesty (Item 4): the object-storage upload
  RUN-outcome field now truthfully reports an executed upload (`true` only on a real
  executed run; `false` on preview/blocked), resolving the self-contradiction with
  `execution_status: executed`. The static contract-preview capability fields are a
  separate signal and are unchanged.
- New `--multipart-threshold` validation/testing aid on `object-storage-upload`
  (Item 5): the 5 GiB default is unchanged; an override is code-bounded to
  `[64 MiB, 5 GiB]` (out-of-band is refused with a blocker). The effective threshold
  and `part_count` are now recorded in the durable upload receipt. The override
  affects only the recorded/used threshold, never the integrity checks.
- `test_remint_reconcile_drifted_snapshot_falls_back_to_content_change` was revised
  (its content subscenarios unchanged; new pure-format subcases added in a sibling
  test that flip to `format_drift`). Two schema fields (`classification_basis`,
  `bom_stripped`) and the retire/upload receipt fields are all additive.

## v0.3.166 - 2026-07-04

- Added a selectable, recorded object-storage upload key strategy plus a safe
  adopt-existing workflow (WOM #11), fixing the false-skip where an object stored
  under a client's own key layout was re-uploaded — or, worse, could be skipped
  against a key it was never at. The new `--key-strategy {sha256_content_addressed,
  prefix}` (default unchanged), `--key-prefix`, and `--key-append-extension` flags
  are available on `object-storage-upload`, `object-storage-upload-plan`,
  `object-storage-upload-verify`, and the new `object-storage-adopt-existing`
  command.
- Two-field key model (additive, no migration): every object-storage location and
  execution receipt now carries a new `remote_key` (the literal bucket-relative
  key the object is/was PUT/HEAD at) alongside the unchanged content-addressed
  `key_hint`. The HEAD-before idempotency check, the skip matcher, and future
  download tooling key off `remote_key`; the digest audits keep validating
  `key_hint`, so no existing location is flagged corrupt.
- Fail-safe idempotency (the one invariant): a skip is legal only when backed by a
  live HEAD proving present-at-the-recorded-key + size-match in the same run. Under
  a live transport the executor ALWAYS re-HEADs the recorded `remote_key` before
  skipping — a recorded key that 404s re-uploads, never silently skips. The re-HEAD
  matches the recorded verification (presence-only for a presence+size adopt,
  checksum for a content-hashed upload), and this live proof OUTRANKS the resume
  ledger's terminal-success short-circuit: once a re-HEAD proves an object absent,
  the re-upload is forced past any stale ledger row, so a wiped remote can never be
  silently skipped from a prior run's ledger. Plan echoes the fully-resolved
  `remote_key` per row and apply refuses (fails closed) if its re-resolved key
  diverges; the plan verdict is strategy-aware so a prior location under a different
  key layout never predicts a skip apply would then re-upload.
- `object-storage-adopt-existing`: a verified adopt (`--approve` + live transport)
  issues a PRESENCE-ONLY HEAD per computed client key (presence + `Content-Length`
  only, no body download) and adopts ONLY on presence + size-match — so adopting a
  large archive costs one HEAD per object, not one download per object (a content
  re-hash would download the whole archive; `--content-hash-verify` is an explicit
  per-object opt-in that GetObject-and-rehashes). A 404 / size-mismatch is not
  adopted, so a wrong prefix/extension self-limits to zero adopts. A declared adopt
  (`--accept-unverified-adopt`, distinct from `--approve`) records a NON-gating
  `declared_uploaded` location that never skips a PUT. Adopt reports
  verified-vs-total so a template miss is visible, never a silent partial. Verified
  adopt is a live surface and honours the same tiny-first tiered gate as the upload
  command: a bulk first-live adopt REFUSES until a single tiny-first `--only` object
  has proved the store.
- The three manifest audits and the execution-receipt doctor audit now accept a
  correct `prefix`-strategy location/receipt without flagging it corrupt, and
  additionally verify that a non-default `remote_key` binds the record's digest
  (kills a valid-looking-but-wrong-object key). The upload evidence writer now
  shares the single content-addressed `key_hint` producer (the duplicate literal
  is gone). The execution-contract preview tells the truth for both strategies
  (the default lands at exactly `sha256/<first2>/<sha256>` with no prefix).
- `remote_key` has its own validator: it holds a path within the bucket (slashes,
  dots, and the archive-id colon are legal) but never a leading slash, `..`, a
  bucket name, an endpoint host, or a URL — leak-checked so public-privacy stays
  green. No archive migration and no hash change; the default strategy is
  byte-identical to before.

## v0.3.165 - 2026-07-04

- Added a normative Plain-Language for Humans convention to the runtime-visible
  operator surfaces: the personal/company/family `AGENTS.md` templates, the
  runtime `wom-archive/SKILL.md` skill, and the
  `wom-ai-runtime-skill-plugin-layer.md` normative doc (with a matching bullet in
  its Skill Template list). When a WOM operator AI addresses a human, it must
  translate git/infrastructure/WOM-internal jargon into everyday language and
  keep the exact technical term in parentheses or in the logs only. The
  convention governs human-facing prose only; machine, JSON, and receipt output
  stays exact and unchanged. It is guidance the reading AI applies, not a code
  check — WOM does not validate plain-language output.
- Extended the read-only `archive ai-response-concept-guide` with a new
  `git_infra_terms` topic and section: a git/infrastructure terminology
  translation layer (fetch, checkout, pin, manifest, hash, commit, tag, branch,
  HEAD, remote, mirror, clone, diff, staged, rebase, stash) with ko-KR/en-US
  everyday phrasings, complementary to the existing WOM operational-term layer.
  The guide adds `git_infra_term_translation_available`, the guide-contract flag
  `translate_git_infra_jargon_for_humans`, and a safe-routing lookup entry. The
  command still writes nothing, calls no providers, and echoes no local paths or
  secret values. Documented as a §5 table in `ai-response-concept-guide.md`.
- No archive migration and no hash change. Guidance and read-only surfaces only.

## v0.3.164 - 2026-07-04

- Added Stage 2 of the live object-storage upload adapter (WOM #11): a real,
  hand-rolled AWS SigV4 R2/S3-compatible transport (`S3CompatibleTransport`).
  It signs the real lowercase-hex payload hash on PUT/UploadPart and
  `UNSIGNED-PAYLOAD` on HEAD/GET, giving each upload SigV4 on-wire body integrity.
  Whole-object integrity is verified by re-download-and-hash — `HeadObject`
  (presence + size) then `GetObject`, re-hashing the returned bytes to the
  lowercase hex the shipped executor compares (the executor comparison itself is
  unchanged). This depends on no provider checksum surface: R2 does not implement
  GetObjectAttributes and marks the `x-amz-checksum-*` headers unimplemented, and
  a SHA-256 multipart checksum can only be COMPOSITE, never the whole-object hash.
  The SigV4 core is pinned byte-exact against the published AWS documented example
  (canonical request, string-to-sign, and signature all match). No dependency was
  added (still PyYAML only); all networking is reachable through one
  `_default_urllib_sender()` seam, and every transport method routes through an
  injected `send`.
- Reliability + cost hardening: a bounded per-object retry loop with exponential
  backoff and jitter to a hard attempt ceiling (`OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT`),
  applied to the multipart path as well as single PUTs; auth errors failing closed
  with zero retries; a real `retry_summary.backoff_ms_total`; a hard cumulative
  provider-PUT ceiling (`OBJECT_STORAGE_TOTAL_PUT_CEILING`) that bounds cost across
  the whole run independent of `--max-objects`; plain multipart with an explicit
  Content-Type per request; and orphan cleanup (`delete_object`) on a
  completed-then-mismatch upload. Backoff sleeps through an injectable seam so tests
  never wall-clock-block.
- Safety: a tiered tiny-first gate (`tiered_gate_unmet`) derived from durable
  execution-receipt facts (successful-receipt count + large-object proof) refuses a
  bulk first-live run until the single-object tier is proved; the direct-value
  secret-containment guard is extended to the derived SigV4 signing key; no request
  headers, `Authorization`, `StringToSign`, `CanonicalRequest`, or provider error
  body is ever recorded.
- Flipped `live_object_upload_adapter_implemented` and
  `provider_api_call_implemented` to true on the upload-adapter surface (the live
  adapter now ships) while keeping capable != automatic: a live `--approve` still
  requires env-only credentials, a safe `--reviewed-by`, a resolvable
  endpoint/bucket, and a met tiered gate. Live signature acceptance by R2 and
  read-after-write consistency of the HEAD+GET verification remain
  `unproven_against_live_provider` until the tiny-first human runbook confirms the
  first live object.

## v0.3.163 - 2026-07-04

- Added the Stage 1 live object-storage upload adapter (WOM #11) as three
  approval-gated CLI commands. `archive object-storage-upload-plan --dry-run`
  composes a content-addressed upload plan with a digest-aware
  `would_upload`/`already_uploaded` verdict; an object is `already_uploaded`
  only when a provider-confirmed `wom_uploaded` manifest location's `key_hint`
  digest matches the object id, never on external `declared_uploaded` evidence
  or a manifest-only hit. `archive object-storage-upload-verify --dry-run`
  hashes each planned object's local RAW bytes and asserts equality with the
  object id (it never normalizes BOM/newlines). `archive object-storage-upload`
  is the mutating command with a three-way gate (reject both modes, reject
  neither, reject `--approve` without a safe `--reviewed-by`), re-enforced at the
  service layer so a direct service/MCP call cannot bypass it.
- NO-NETWORK BOUNDARY: this release ships no transport that performs a socket
  operation. The upload spine calls a provider only through an injected
  `ObjectStorageTransport`; Stage 1 ships the abstract interface plus a
  `NullTransport` whose every method raises, and `object_storage_resolve_transport`
  returns null for every provider. `object-storage-upload --approve` therefore
  fails closed with `live_transport_not_implemented` before any credential read
  or byte read. `live_object_upload_adapter_implemented` and
  `provider_api_call_implemented` are both false. Making a real PUT requires a
  Stage-2 code change that adds an import and rewires the resolver — it cannot
  land silently. No new dependency was added (still PyYAML only).
- Hardened the shared object-storage manifest writer
  (`update_manifest_with_object_storage_upload_evidence`, used by the existing
  upload-evidence command): it now holds the shared manifest lock and writes via
  a temp+fsync+`os.replace` atomic writer, so a crash mid-write or a concurrent
  objet-capture can no longer corrupt the manifest. This fix is additive and
  benefits the existing evidence command too.
- Secret discipline is a direct-value containment guard: both resolved key
  values are compared as substrings against the fully-serialized output on every
  exit path before any write, backed by the existing regex/location scanners.
  Execution receipts and the crash-safe append-only resume ledger are built from
  a fixed scalar allowlist, never from provider bodies or caught exception args;
  no request headers, `Authorization`, `StringToSign`, `CanonicalRequest`, or
  provider error body is ever recorded.
- Added a doctor check for object-storage execution receipts, a new
  `object-storage-upload-receipt.schema.json`, and read-only MCP tools
  `object_storage_upload_plan` and `object_storage_upload_verify`. This is Stage
  1 of a staged rollout; the adapter cannot upload to a provider yet.

## v0.3.162 - 2026-07-03

- Added `archive remint-reconcile`, an honest mint-receipt reconcile that
  re-issues a mint receipt's recorded sha256 values after a canonical zettel
  drifts (for example a CRLF/BOM re-checkout, or a human content edit). The
  command classifies the drift as `format_drift` (newline/BOM only) or
  `content_change` and always shows the current on-disk content. Governing
  doctrine (recorded in the v0.3.162 decision log): reconcile never masks
  corruption and classification never waives human review. Every `--approve`
  requires `--reviewed-by`; a `content_change` also requires an explicit
  `--content-changed-ack`; hard refusals (id mismatch, non-mint receipt,
  unparseable/ non-canonical target, missing receipt) run before any
  classification, so a corrupt state is refused, never "fixed."
- `format_drift` is granted only on positive, byte-level, re-derivable proof:
  the current canonical body must be identical to a clean draft snapshot AND the
  FULL content frontmatter re-derived from that snapshot must match the current
  canonical field-by-field (every draft key, with `source_refs` mint-transformed,
  excluding only the mint-injected `status`/`updated_at`/`mint`/`promotion` keys;
  `status` is separately required to equal `canonical`). Because every content
  field is compared and not a hand-picked subset, an edit to ANY field (title, id,
  kind, visibility, facets, provenance, edges, created_at, …) is caught. A
  drifted, missing, or BOM'd snapshot is never treated as a clean anchor and falls
  back to the stricter `content_change` path. A canonical-only title or field edit
  is therefore correctly classified as `content_change`.
- Reconcile writes BOTH an in-place mint-receipt update (recomputed shas plus an
  append-only `reconcile.history` provenance block, including a
  `normalized_content_digest`) AND a separate immutable audit receipt under
  `receipts/mint/reconciles/`. Both writes are atomic (temp file + os.replace).
- `archive doctor` now routes a canonical byte-drift to reconcile: a
  previously-reconciled receipt that re-drifted by newline/BOM only emits the new
  `mint_receipt_target_byte_drift_suspected_format` ERROR; an un-reconciled
  sha mismatch keeps the plain `mint_receipt_sha_mismatch` ERROR with a
  suggested `remint-reconcile --dry-run` command. Both stay non-clean (fail
  `doctor` and `--strict`); the edge-receipt evolution path is unchanged. A
  UTF-8 BOM on a canonical zettel now surfaces a `zettel_has_bom` WARN advisory.
- `archive retire-draft` now surfaces a `remint-reconcile --dry-run` next-safe
  action when — and only when — retirement is blocked by the mint-target
  sha-mismatch blocker. No retire gate was relaxed.
- Additive parse tolerance (no hash changes, no archive migration): frontmatter
  parsing and receipt/JSON reads now tolerate a leading UTF-8 BOM
  (`utf-8-sig` / one-BOM strip). sha256 hashing still reads raw bytes, so BOM and
  newline drift stay visible. New mints pin the canonical write to LF newlines to
  prevent immediate re-drift. Added the `mint-reconcile-receipt` schema and a
  `reconcile` property on the mint-receipt schema (not required; legacy receipts
  are unaffected).

## v0.3.161 - 2026-07-03

- Restructured README.md and README.ko.md (docs-only, no behavior change).
  After ~160 one-append-per-release batches the READMEs had accreted a
  49-line "Earlier public baseline" ladder, "What exists today" bullets that
  had grown into 1,600-3,900-character run-on sentences, and a ~200-tag
  release list in the Versioning section.
- The Status section now carries only the current-baseline code block, ONE
  previous-baseline line, and a single "Full release history" pointer to
  CHANGELOG.md and `wom-kit/docs/releases/`; the roadmap-snapshot paragraph
  and the not-production-ready sentence are unchanged.
- "What exists today" became a "What Exists Today" section with nine thematic
  subsections (Archive core & lifecycle; Capture & intake; Retrieval & views;
  Sharing & ZET previews; Privacy & redaction; AI-operator contracts &
  runtime handoff; Provider integrations; Credentials & setup guidance;
  Hygiene & release tooling). Every capability claim from the old monster
  bullets survives as a shorter bullet; the section keeps its single pointer
  to the WOM-kit Capability Matrix for the status-by-capability view. No
  capability claims were added or dropped (claim mapping recorded in the
  v0.3.161 decision log).
- The Versioning section keeps its two intro sentences and now states the
  current checkpoint tag, that every release is tagged, and where the full
  tag history lives (CHANGELOG.md, VERSIONING.md, GitHub releases), plus a
  compact paragraph for the checkpoint baselines that earlier release notes
  still reference; the per-line tag list is deleted. README.ko.md received
  the same restructure as a real Korean rendition, not a machine-literal
  translation.
- Adopted the README maintenance contract (recorded in the v0.3.161 decision
  log and as an HTML comment at the top of each Status section): per release,
  update ONLY the current-baseline line, the one previous-baseline line, and
  (for feature releases) at most ONE thematic bullet; release history lives
  in CHANGELOG.md and `wom-kit/docs/releases/`.

## v0.3.160 - 2026-07-03

- Added the AI Intake Protocol to every runtime-visible surface
  (personal/family/company AGENTS.md templates, the fake-life-archive example
  AGENTS.md, `templates/ai-runtime/wom-archive/SKILL.md`, and
  `docs/wom-ai-runtime-skill-plugin-layer.md`): BEFORE physically copying any
  local file into the archive or an objet store — not just before drafting —
  run `archive source-intake <archive-root> --dry-run --local-path <file>`,
  stage inside the archive root, and route captures only through the reviewed
  `objet-capture-selection` -> `objet-capture` approval chain (real archives
  also need `objet-capture-enable`; bulk external stores go through
  `prehashed-objet-ledger` plus `object-storage-upload-evidence` instead of
  per-file copies).
- Added two additive read-only doctor warnings:
  `archive_objets_layout_noncanonical` fires whenever a raw in-root `objets/`
  folder exists (the D2 layout signal; deliberately NOT silenced by
  gitignoring the folder, because ignored originals silently drop out of the
  git-push backup path), and `workspace_objet_store_git_exposure` fires when
  an objet byte store (in-root `objets/` or the sibling `<root-name>-objets`
  store) sits inside a git working tree whose ignore rules do not plainly
  exclude it. Detection is filesystem-cheap and fail-quiet: stores and
  archives that are their own VALID git repos never warn (a `.git` dir with
  `HEAD`, or a worktree/submodule `gitdir:` pointer file whose target exists
  with `HEAD`), while a BROKEN marker — empty `.git` dir, dangling pointer —
  is ignored by real git and counts as ambiguous, so the guard still warns;
  bare repositories never warn, the valid archive-is-its-own-repo case stays
  silent (the archive `.gitignore` completeness check owns that signal), and
  the sibling store's contents are never enumerated. Anchored `.gitignore`
  lines only silence the warning from the store's own parent directory (an
  anchored repo-root line does not match a nested store in git), and the fix
  hint names the anchored or unanchored form accordingly. The exposure
  message names the store's basename only — never a local absolute path.
- Added the anchored `/objets/` pattern to the recommended archive
  `.gitignore` defaults (`init`, `repair-gitignore`, doctor's completeness
  check, `tools/check_artifact_hygiene.py`, and the fake-life-archive
  fixture). Anchoring is deliberate: nested `objets/` folders inside staged
  client trees keep their normal handling.
- Ruled the official intake layout (D2, dev-team decision, 2026-07-03):
  canonical capture intake stages INSIDE the archive root under
  `staging/incoming/<YYYY-MM-DD>/` (date layer recommended, not required);
  the sibling `-objets` store is for bulk external originals under
  never-touch protection with prehashed-ledger evidence; a raw in-root
  `objets/` folder is non-canonical, with a register-then-capture migration
  guide in `docs/artifact-hygiene.md`. `project_intake_staging_convention`
  (the shared check behind project-intake-plan and
  project-intake-unpack-queue) now accepts in-archive `staging/incoming/`
  staging as `matches_recommended_shape` with additive `matched_shape` /
  `recommended_in_archive_shape` fields, and project-intake-staging-guide
  (which takes no staged folder) recommends the same in-archive shape for
  capture intake, so the runtime no
  longer contradicts the documented canonical location; the affected docs
  (artifact-hygiene, project-intake-session, source-object-storage-policy,
  project-intake-cookbook, ai-assisted-onboarding-and-provider-setup,
  new-user-flow, objet-storage-strategy, wom-ai-runtime-skill-plugin-layer)
  now carry one consistent three-way statement.
- Added `archive operator-feedback-plan` to the runtime discovery chain:
  `runtime_context_recommended_first_commands` (appended fourth entry),
  `ai_runtime_order` (new step 7 `plan_operator_feedback`), and
  `RUNTIME_CONTEXT_SAFE_ACTIONS` (`run operator-feedback-plan dry-run`), plus
  shipped the missing schema files
  `wom-kit/schemas/operator-feedback.schema.json` and
  `wom-kit/schemas/operator-feedback-receipt.schema.json` matching the
  existing record/receipt shapes (schema-id strings unchanged), with schema
  conformance tests that validate a real produced record and receipt and
  reject subset-covered breakage (const/enum/required/type).

## v0.3.159 - 2026-07-03

- Added paired transcript intake: a selection-manifest item MAY carry a
  `derived_text` sub-object (`staged_text_path`, `approved_text_sha256` over
  the RAW file bytes, `derivation_kind`, `tool_name`, `tool_version`,
  `review_status`, plus optional model/confidence/language/born_digital), so
  ONE human approval covers both the staged original and its already-extracted
  transcript. `objet-capture-selection` gains the pairing flags
  (`--derived-text-staged-path`, `--derivation-kind`, `--tool-name`,
  `--tool-version`, `--review-status`, `--model-name`, `--model-version`,
  `--confidence`, `--language`, `--born-digital`).
- Paired manifests use the NEW action string
  `local_objet_capture_with_derived_text_approved` and schema
  `wom-kit/b4-selection/v0.3`; pre-0.3.159 kits refuse them with
  `selection_action_invalid` instead of silently dropping the derived half
  (fail-closed by design). Plain manifests keep the old action and the v0.2
  schema; the envelope validator now validates the `schema` field for the
  first time (`selection_schema_invalid`).
- `objet-capture --approve` runs in two phases inside one lock: originals
  publish and their manifest lines are flushed+fsynced FIRST, then each
  derived half registers through the derive-text store bound to the minted
  `object_id` (`paired_with` back-link on the derived receipt). A blocked
  original never reads its transcript (`blocked_by_original`); a failing
  derived half never aborts the run (`derived_text_registration_failed`) and
  reports item/run `status_class: partial` with re-run repair guidance.
- Added deterministic BOM-only encoding handling to derived-text capture
  (standalone, batch, and paired): BOM-marked UTF-8 (`utf-8-sig`) and UTF-16
  LE/BE decode strictly and are stored as BOM-less UTF-8 with line endings
  preserved; UTF-32 BOMs block with `text_file_bom_encoding_unsupported`;
  BOM-marked-but-undecodable input blocks with
  `text_file_bom_encoding_undecodable` (+ `detected_bom`); decoded text
  containing U+0000 blocks with `text_file_contains_nul`; BOM-less non-UTF-8
  keeps `text_file_not_utf8` with an extended hint. `source_text_encoding` and
  `source_text_sha256` (raw bytes) are recorded in record provenance and
  receipts; identity/verification stay keyed to the STORED UTF-8 bytes.
- utf-8-sig identity change (NOT additive): previously the UTF-8 BOM survived
  validation and raw bytes were stored WITH the BOM; the BOM is now stripped,
  so the same utf-8-sig input yields a different `text_sha256`/
  `derived_text_id` than before and a post-upgrade re-run creates a second
  record instead of `skip_already_present`.
- Added `DERIVED_TEXT_MAX_SOURCE_BYTES` (64 MiB) with blocker
  `text_file_too_large`, checked on the fstat size before reading; hardened
  the standalone `--text-file` reader to an O_NOFOLLOW-fd + fstat read.
- Schema bumps: `objet-capture` receipt v0.2 -> v0.3 (items carry the
  `derived_text` sub-result, `status_class`, derived summary counters);
  derived-text capture receipt v0.1 -> v0.2 (`source_text_encoding`,
  `source_text_sha256`, `paired_with` on paired runs). The derived-text
  RECORD schema stays v0.1 with additive optional provenance fields.

## v0.3.158 - 2026-07-03

- Added `archive objet-capture-enable` (alias `archive capture-enable`): an
  explicit, receipted, revocable owner consent flow that lets a real
  (non-sandbox) archive run local objet capture. `--dry-run` returns a
  read-only eligibility report (`state`, orthogonal `never_touch_name_match`,
  `planned_writes`, `reason` for invalid records) and writes nothing;
  `--approve --reviewed-by <actor>` evaluates every blocker before any write,
  then writes the receipt first and the singleton
  `ops/capture-enablement.yml` record second; `--revoke --approve` flips the
  record to `enabled: false` with `revoked_by`/`revoked_at`. Pattern-matched
  root names require `--acknowledge-never-touch-name`; re-approving over a
  revoked record requires `--reenable`. CLI-only; not exposed via MCP.
- Reworked the objet-capture gate order so a valid enablement record allows
  capture before the never-touch name check, with strict validity (exact
  schema/scope/statement match, `archive_id` binding, `enabled is True`
  boolean identity, acknowledgment on pattern-matched roots) and fail-closed
  behavior on any read or validation exception.
- Made the per-item never-touch checks enablement-aware: validly-enabled roots
  evaluate the name pattern on archive-relative components only, so the
  enabled root's own name no longer re-blocks every item while matching
  components below the root still block with `resolved_path_never_touch`.
  Non-enabled roots are unchanged, and the shared
  `target_looks_external_live_never_touch` check is identical in both copies.
- Added the additive refusal field `enablement_state`
  (`absent`/`invalid`/`revoked`/`disabled`) to `objet-capture` refusals; the
  `blocked_by` ids are unchanged and refusals stay blocker-only.
- Updated both objet-capture refusal hints to route owners to
  `archive objet-capture-enable <archive-root> --dry-run` (read-only) instead
  of calling real-archive enablement a separate planned flow.
- Added doctor diagnostics for the enablement record: INFO
  `capture_enablement_enabled` / `capture_enablement_revoked`, WARN
  `capture_enablement_record_invalid` (with the reason) and
  `capture_enablement_receipts_missing`; the WARNs fail strict validation.
- Documented the consent model, record/receipt schemas, forward-only
  revocation, and the no-overclaim Safety Boundary in
  `wom-kit/docs/capture-enablement.md`, and swept stale sandbox-only wording
  from source-intake guidance, CLI help, the capability matrix, the
  project-intake session doc, and the artifact-hygiene gaps list.
- Updated README status, capability matrix checkpoint, upgrade guides, release
  notes, and CLI tests.

## v0.3.157 - 2026-07-03

- Fixed stale `source-intake` guidance that predated local objet capture
  (v0.3.2): `candidate_unmanifested` next safe actions now route to
  `objet-capture-selection`, `objet-capture --selection <selection-path>
  --dry-run`, and the `prehashed-objet-ledger` /
  `object-storage-upload-evidence` external-evidence path instead of telling
  operators to wait for a future capture flow.
- Named the real commands in `source-intake` warnings: the missing
  object-storage warning now points at `archive object-storage --dry-run`, and
  the source-root warning now points at `archive add-source`.
- Stopped emitting the "outside registered source roots" warning for files that
  already resolve inside the archive root; it now fires only for genuinely
  external files.
- Added static, selection-independent `hint` strings to `objet-capture`
  refusals for `sandbox_marker_required` and `external_live_never_touch` while
  keeping the blocker-only refusal contract (no filenames, provenance, or
  receipt paths).
- Added `.m4a` -> `audio/mp4` (the standard MP4-audio mime) to the
  deterministic objet-capture mime map; `source-intake` records the same value
  where the platform mimetypes database maps `.m4a`.
- Corrected the artifact-hygiene "Current Gaps" doc: local objet capture exists
  (v0.3.2+) for sandbox-marked archives; only real-archive capture enablement
  is still future work.
- Updated README status, capability matrix checkpoint, source-intake planner
  doc, release notes, and CLI tests.

## v0.3.156 - 2026-06-25

- Added top-level `status_class`, `input_provenance_class`,
  `secret_signal_class`, and `operator_envelope` fields to the core read-only
  operator commands `operation-status-taxonomy`, `input-provenance-taxonomy`,
  `secret-signal-taxonomy`, and `ai-response-contract`.
- Added the `wom-kit/operator-envelope-classes/v0.1` schema marker for those
  fields.
- Documented the first operator-envelope retrofit checkpoint.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.155 - 2026-06-25

- Added read-only `archive ai-response-contract`, with aliases
  `archive response-contract` and `archive operator-response-contract`, to
  define the minimum status/provenance/privacy/approval checks an AI operator
  should apply before answering a human.
- The contract explicitly allows a compact conversational status board and
  states that no web UI is required.
- It ties together operation status, input provenance, secret-signal handling,
  approval handoff audits, and archive status-board checks without reading
  archive body text or writing files.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.154 - 2026-06-25

- Added read-only `archive secret-signal-taxonomy`, with aliases
  `archive secret-taxonomy` and `archive sensitive-signal-taxonomy`, to define
  class-aware secret and sensitive-signal handling for AI operators.
- Added explicit signal classes:
  `concept_word`, `safe_reference`, `credential_reference`,
  `secret_value_pattern`, `private_locator`, `account_identifier`, and
  `unknown_sensitive_context`.
- Marked concept words, safe references, and credential references as not
  blocking by themselves.
- Marked secret-like values, private locators, account identifiers, and unknown
  sensitive context as blocking classes for public outputs.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.153 - 2026-06-25

- Added read-only `archive approval-handoff-audit`, with aliases
  `archive handoff-audit` and `archive human-approval-handoff-audit`, to audit
  a handoff record before a future operation uses it as approval evidence.
- The audit checks record path boundary, schema, expected status, expected
  operation kind, `reviewed_by` presence for `approved_once`, and closed-action
  safety flags.
- The audit returns `future_operation_authorized: true` only for a matching
  `approved_once` handoff.
- Kept the audit execution-safe: it reads only handoff metadata, executes no
  operation, reads no private material, calls no providers, and echoes no
  target ref or requested action values.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.152 - 2026-06-25

- Added read-only `archive input-provenance-taxonomy`, with aliases
  `archive provenance-taxonomy` and `archive caller-input-taxonomy`, to define
  how AI operators should label the origin of command inputs.
- Added explicit provenance classes:
  `tool_discovered`, `receipt_verified`, `human_selected`, `caller_supplied`,
  `ai_generated`, `fixture_supplied`, `environment_inferred`, and `unknown`.
- Marked caller-supplied, AI-generated, fixture-supplied, environment-inferred,
  and unknown inputs as unverified source truth.
- Added AI operator checks so supplied inputs are not described as
  tool-discovered or receipt-verified.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.151 - 2026-06-25

- Added read-only `archive operation-status-taxonomy`, with aliases
  `archive status-taxonomy` and `archive partial-success-taxonomy`, to define
  how AI operators should classify operation results before reporting work as
  complete.
- Added explicit status classes:
  `succeeded`, `preview`, `written`, `no_change`, `partial`, `truncated`,
  `blocked`, and `failed`.
- Marked `partial`, `truncated`, `blocked`, and `failed` as not-success classes
  so item-level gaps, limit caps, blockers, and unexpected errors are not
  summarized as full success.
- Added AI operator checks for `truncated=true`, `limit_hit=true`,
  `omitted_count>0`, `incomplete_count>0`, dry-run mode, and privacy guards.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.150 - 2026-06-25

- Added read-only `archive approval-handoff-plan`, with aliases
  `archive handoff-plan` and `archive human-approval-handoff-plan`, to define
  the AI-to-human approval handoff storage and status lifecycle.
- Added approval-gated `archive approval-handoff-record`, with aliases
  `archive handoff-record` and `archive human-approval-handoff-record`, to
  write `ops/approval-handoffs/<handoff-id>.yml` metadata plus a receipt under
  `receipts/approval-handoffs/`.
- The approval handoff lifecycle now has explicit statuses:
  `needs_review`, `approved_once`, `denied`, `superseded`, and `resolved`.
- Added operation kinds for private material reads, archive writes, external
  provider actions, releases, credential access, derived artifact updates, and
  other reviewed operations.
- Kept the handoff body-safe and execution-safe: it does not execute the
  underlying operation, read private material, call providers, check network,
  read secrets, echo target refs, or echo requested action values.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.149 - 2026-06-25

- Added read-only `archive operator-feedback-plan`, with aliases
  `archive feedback-plan` and `archive ops-feedback-plan`, to define the
  storage and status lifecycle for operator-generated tool feedback.
- Added approval-gated `archive operator-feedback-record`, with aliases
  `archive feedback-record` and `archive feedback-register`, to write
  `ops/feedback/<feedback-id>.yml` metadata plus a receipt under
  `receipts/operator-feedback/`.
- The feedback lifecycle now has explicit statuses:
  `draft`, `delivered`, `acknowledged`, `resolved`, and `archived`.
- Kept the command body-safe and local-only: it does not read feedback bodies,
  copy files, submit externally, call providers, check network, echo feedback
  refs or titles, or treat user knowledge `objets/` as the lifecycle tracker.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.148 - 2026-06-25

- Added read-only `archive capabilities --machine` for AI operators that need
  to know which WOM-kit commands are executable in the current local
  installation before planning a workflow.
- The manifest is generated from the actual local CLI parser and reports
  command names, aliases, help text, required positionals, options, nested
  subcommands, command count, version, release notes presence, local git tag
  presence, and local release state.
- The command uses a stable agent-facing envelope:
  `ok / state / summary / data / blockers / warnings / privacy_guards`.
- Kept the command read-only and local-only: it writes nothing, calls no
  providers, checks no network, and echoes no local absolute paths, tokens, or
  secret values.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.147 - 2026-06-25

- Added read-only `archive derived-artifact-staleness`, with aliases
  `archive report-staleness` and `archive artifact-staleness`, to check
  whether declared `derived_artifacts` may be stale because a source zet is
  newer than the artifact's last reviewed sync timestamp.
- The check reports stale artifacts, missing `source_zettels`, unresolved
  source zettel refs, and unknown sync timestamps without opening external
  report bodies or writing archive files.
- Kept the output privacy-safe: it does not echo artifact refs, zet titles,
  zettel body text, provider URLs, local absolute paths, tokens, or secret
  values.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.146 - 2026-06-25

- Added read-only `archive status-board`, with aliases
  `archive archive-status-board` and `archive zet-status-board`, to summarize
  archive state for beginners without requiring them to inspect `inbox/`,
  `zettels/`, mint receipts, and draft snapshots manually.
- The status board reports counts and limited path/id examples for canonical
  zets, active drafts, minted drafts pending `retire-draft`, missing document
  type/audience metadata, source metadata gaps, derived artifact source/sync
  gaps, and optional body-inspecting quality attention counts through
  `--include-quality`.
- Added next-action guidance for common cleanup and metadata review paths,
  including pending draft retirement, source metadata review, and derived
  artifact sync review.
- Kept the command read-only and privacy-safe: it writes nothing and does not
  echo zet titles, body text, source-ref values, provider URLs, local absolute
  paths, tokens, or secret values.
- Updated README status, capability matrix, public docs, release notes, and CLI
  tests.

## v0.3.145 - 2026-06-25

- Added read-only `archive zet-quality-check`, with alias
  `archive zettel-quality-check`, to inspect one draft or canonical zet for
  entity-term, document-type, OCR/parse metadata, table-structure,
  correction-event, source-rights, audience, and derived-artifact dependency
  risks before mint.
- Added optional `zet-quality-rules.yml` project entity rules. A forbidden
  entity alias rule can become a mint blocker, while command output reports
  only safe rule ids/counts and does not echo matched terms, source values,
  body text, provider URLs, or local paths.
- `mint-zet --dry-run` now includes the same `quality_check` summary and
  blocks only when the quality check reports blocker-severity issues.
- `archive doctor` now warns when archive roots contain top-level web/app
  development artifacts or an incomplete `.git` marker, helping operators keep
  generated report apps outside WOM archive roots.
- Added `node_modules/`, `.next/`, and `.vercel/` to generated archive
  `.gitignore` defaults and artifact hygiene policy.
- Updated README status, capability matrix, public docs, release notes, fake
  archive fixtures, and CLI/hygiene tests.

## v0.3.144 - 2026-06-22

- Added read-only `archive zet-self-contained-check` to report whether a
  selected zet depends on AI scratch refs, private provider locators, local
  absolute paths, or object-store locations.
- Added approval-gated `archive ai-scratch-gc`, with aliases
  `archive ai-residue-cleanup` and `archive scratch-gc`, to delete only
  explicit `.wom-scratch/` or `workbench/ai-scratch/` files referenced by one
  selected zet and write a cleanup receipt.
- Updated minting so public external citation URLs may remain in zet bodies or
  `source_refs`, while private provider locators and original-file locations
  remain blocked by the machine-enforced `object_id_only` gate.
- Approved `mint-zet` now removes explicit AI scratch refs from the canonical
  zet and invokes the same scratch cleanup gate after canonical, mint receipt,
  and draft snapshot writes succeed.
- Added `.wom-scratch/` and `workbench/ai-scratch/` to generated archive
  `.gitignore` safe defaults and artifact hygiene classification, while keeping
  broad archive-wide scratch sweeps as future work.
- Updated README status, artifact hygiene docs, capability matrix, release
  notes, and tests.

## v0.3.143 - 2026-06-22

- Added approval-gated Tiro credential reads from Windows Credential Manager
  through safe `keyring:` and `credential-manager:` refs in
  `archive tiro-lossless-recovery-fetch-run`.
- Dry-run still opens no credential store and calls no provider. Approved mode
  may read the local OS credential store only after `--approve --reviewed-by`,
  then clears the token from local runtime variables before returning.
- The Windows reader first tries an exact generic credential target match. If no
  exact target exists, it can auto-detect exactly one matching generic
  credential from the safe ref label; multiple matches block without echoing
  target names.
- Tiro credential values may be raw bearer/API tokens or JSON-shaped OAuth
  credential blobs with `access_token` / `accessToken`-style fields; command
  output and receipts echo no refs, env var names, OS credential target names,
  tokens, provider URLs, account ids, emails, or raw provider responses.
- Updated the Tiro lossless recovery docs, capability matrix, README status,
  release notes, and tests.

## v0.3.142 - 2026-06-22

- Added read-only `archive notion-oauth-connection-preflight`, with aliases
  `archive notion-oauth-preflight` and
  `archive notion-connect-oauth-preflight`, to validate the secret-blind local
  OAuth runtime contract before a future live Notion browser connection flow.
- The preflight checks safe client id/client secret refs, local loopback
  callback URI shape, optional one-time state storage, and keyring/secret/wallet
  token-store intent while rejecting plain env token storage for OAuth access
  and refresh tokens.
- The output keeps the AI secret-blind: it does not read credentials, open a
  browser, start a callback server, generate an authorization URL, exchange a
  code, store tokens, call Notion, or echo exact refs, redirect URI, provider
  URLs, tokens, account ids, or emails.
- Updated the Notion connection plan, capability matrix, README links, public
  documentation maps, release notes, and tests.

## v0.3.141 - 2026-06-22

- Added read-only `archive notion-connection-plan`, with aliases
  `archive notion-connect-plan` and `archive notion-one-click-connection-plan`,
  to record the one-click Notion connection product contract after the
  beta-tester recovery UX breakdown.
- The plan separates Notion internal connections, personal access tokens, and
  public OAuth connections, and names public OAuth/managed local connection as
  the target product direction while keeping env/file token handoff as a
  power-user fallback.
- Notion live ancestor fetch failures now keep raw provider errors redacted but
  classify safe action categories such as invalid token, permission/page-share
  gap, missing or unshared object, rate limit, network timeout, and temporary
  provider outage.
- `archive notion-recover` now surfaces those safe categories and suggested
  human actions in its fetch summary instead of only saying that every provider
  check failed.

## v0.3.140 - 2026-06-22

- Added approval-gated `archive tiro-lossless-recovery-fetch-run`, with alias
  `archive tiro-recovery-fetch-run`, to call the official Tiro REST API from a
  local `env:` credential ref and write a private raw recovery bundle under
  `workbench/`.
- The live fetch command supports dry-run preview without reading credentials,
  approved env-token execution, pagination capture, raw bundle writing, and a
  non-secret fetch receipt under `receipts/tiro/lossless-fetches/`.
- Command output and receipts report counts, archive-relative paths, and gap
  categories, but do not echo credential refs, environment variable names,
  tokens, meeting titles, transcript text, participant names, provider URLs, or
  raw provider responses.
- The remaining Tiro recovery gaps are explicit: audio original byte retrieval,
  keyring/vault credential reads, and AI enrichment writes are still separate
  future layers after raw bundle preservation.

## v0.3.139 - 2026-06-22

- Added read-only `archive tiro-lossless-recovery-plan` for the official Tiro
  full-data recovery surface: workspaces, notes, paragraphs, summaries,
  generated documents, templates, folders, word memories, wiki data, share
  links, translations, audio availability/gaps, pagination, rate-limit, and
  error observations.
- Added approval-gated `archive tiro-lossless-recovery-capture` to preserve a
  reviewed raw Tiro recovery JSON bundle as a content-addressed WOM objet with
  a non-secret receipt and object manifest record.
- The Tiro recovery capture path preserves raw bundle bytes exactly while
  command output and receipts avoid echoing meeting titles, transcript text,
  participant names, emails, provider URLs, tokens, or secret values.
- Added read-only `archive zet-markdown-style-guide` and wired the same
  range-tilde rule into `archive ai-response-concept-guide --topic all`: use
  `A ~ B` for ranges, and reserve double tilde for intentional Markdown
  strikethrough.

## v0.3.138 - 2026-06-22

- Added a CLI-only `file:<path>` credential fallback to `archive
  notion-recover`, so a human who already has a local Notion token text file can
  point to it without pasting the token into a hidden prompt or building an
  environment-variable command.
- The wrapper reads the token locally, passes it through the existing
  approval-gated Notion ancestor fetch adapter chain, restores any prior
  transient process value afterward, and keeps the AI outside the secret path.
- Updated dry-run output, beginner setup guidance, the capability matrix, README
  summaries, and release notes to distinguish implemented file-ref fallback from
  planned vault/keyring one-click live reads.
- Added CLI coverage proving `file:<path>` succeeds against the fake Notion
  adapter while command output does not include the token file path, file name,
  transient env ref, token value, receipt paths, provider URLs, local paths,
  account ids, emails, tokens, or secret values.

## v0.3.137 - 2026-06-22

- Added read-only `archive tiro-import-plan` and MCP `tiro_import_plan` for
  Tiro-style meeting transcript import planning from archive-internal
  manifests.
- The Tiro planner validates meeting metadata, speaker turns, timestamps,
  transcript segment shape, confidence fields, and optional audio objet refs
  without echoing meeting titles, participant names, transcript text, source
  URLs, audio filenames, local paths, account ids, emails, tokens, or secrets.
- Added a public fake archive Tiro manifest fixture and documentation for the
  manifest contract and safety boundary.
- Strengthened `archive version` with `project_source_mirror` checks so
  project-local `.zettel-kasten/source` mirrors can report source version,
  pyproject version, installed-version pin alignment, exact head tag, and latest
  fetched semver tag drift when available.

## v0.3.136 - 2026-06-22

- Added `archive notion-recover`, a beginner-facing one-command wrapper for
  Notion missing-location recovery.
- The wrapper auto-selects a reviewed missing-location tree fixture, asks for
  local confirmation, accepts the Notion token only through a hidden local
  terminal prompt or already available local process value, writes the
  one-time approval receipt internally, runs the approved location fetch, writes
  a sanitized ancestor result fixture, and returns an AI handoff sentence for
  tidying and merge review.
- Preserved the lower-level `notion-ancestor-crawl-plan`,
  `credential-access-approval`, `notion-ancestor-fetch-adapter-run`, and
  `notion-ancestor-merge-plan` commands for power users and automation.
- Updated the beginner setup manual, capability matrix, README links, and
  public documentation map so the human path starts with `archive
  notion-recover` instead of page-id/env/receipt copy-paste chains.
- Added CLI tests for dry-run auto-scope and approved approval->fetch->merge
  chaining, including checks that token values, env names, receipt paths,
  provider URLs, raw refs, page titles, page bodies, and local paths are not
  echoed.

## v0.3.135 - 2026-06-22

- Added read-only `archive beginner-setup-manual --topic
  notion_nested_recovery --dry-run`.
- The new guide translates low-level Notion recovery terms such as
  ancestor/parent/child, fetch/crawl, fixture/node, merge, and untraceable into
  folder/shelf/location language before showing commands.
- It walks a beginner through scoped review, private local token ref setup,
  one-time credential approval preview/write, live structure fetch preview/run,
  and `notion-ancestor-merge-plan` handoff.
- It remains read-only: no approval receipts are written, no environment
  variables are read, no Notion provider calls are made, no live fetch runs, and
  no page titles, page bodies, comments, media bytes, signed file URLs, raw
  provider responses, exact env var names, account emails, provider URLs,
  tokens, or secret values are echoed.

## v0.3.134 - 2026-06-22

- Added approval-gated local
  `archive notion-ancestor-fetch-adapter-run --dry-run|--approve`.
- The adapter verifies a matching credential access approval receipt and
  credential policy check, supports `env:` token refs through the local CLI
  process in this first version, calls the Notion API only for parent-chain
  structure metadata, and writes a sanitized
  `notion_ancestor_result_fixture` plus a non-secret execution receipt.
- The run stops at known generation roots, workspace roots, max depth,
  ambiguous parents, unsafe refs, or redacted provider fetch failures, then
  routes the next step to `notion-ancestor-merge-plan`.
- Still closed: no MCP live provider-call tool, OAuth, browser session,
  keyring/password-manager reads, page title/body/comment reads, signed URL
  refresh, media byte download/hash, zettel writes, edge writes, minting, or
  object manifest updates.

## v0.3.133 - 2026-06-22

- Clarified the Notion ancestor live adapter contract in
  `archive notion-ancestor-fetch-adapter-execution-contract --dry-run` and MCP
  `notion_ancestor_fetch_adapter_execution_contract`.
- The future live ancestor adapter must recurse upward from each
  `crawl_request_queue` seed until a stop condition such as known generation
  root, workspace root, max depth, ambiguous parent ref, or unsafe ref.
- Added JSON scope guidance and warning output so generation-unknown
  untraceable leaf recovery is scoped by leaf/root/ancestor refs rather than
  generation id when the generation has not yet been recovered.
- Still closed: no live Notion fetch adapter, OAuth, provider API calls,
  credential value reads, title/body reads, media downloads, fixture writes,
  zettel writes, edge writes, receipts, or object manifest updates.

## v0.3.132 - 2026-06-22

- Added read-only
  `archive notion-media-fetch-adapter-execution-contract --dry-run` and MCP
  `notion_media_fetch_adapter_execution_contract`.
- The media fetch contract reuses nested-tree planning to scope candidate live
  content leaf pages, defines the future `notion_media_result_fixture`, requires
  fresh provider file refs and byte hashing before preservation claims, and
  keeps the v0.3.131 actor boundary: WOM local credential-bounded adapter,
  human credential approval, AI plan/review/verify only.
- Added read-only
  `archive notion-media-result-verification-plan --dry-run` and MCP
  `notion_media_result_verification_plan`.
- The verifier checks sanitized media result fixtures against
  `objects/manifests/files.jsonl` for `object_id` / `sha256` consistency,
  manifest presence, and preservation states: `already_preserved`,
  `newly_preserved`, and `fetch_failed`.
- Still closed: no live Notion media fetch adapter, OAuth, provider API calls,
  credential value reads, signed URL refreshes, media byte downloads, media byte
  hashing, object manifest writes, receipts, zettel writes, edge writes, or
  object manifest updates.

## v0.3.131 - 2026-06-22

- Clarified the Notion ancestor fetch adapter execution subject in
  `archive notion-ancestor-fetch-adapter-execution-contract --dry-run` and MCP
  `notion_ancestor_fetch_adapter_execution_contract`.
- Added `execution_actor_contract` to state that the current live fetch subject
  is none, the intended future subject is a WOM local credential-bounded adapter
  process, the AI chat runtime may only plan/review/verify, and credential
  values must stay outside AI context.
- Clarified that client-supplied `notion_ancestor_result_fixture` files are
  accepted only as sanitized safe-origin fallback input; the contract does not
  require clients or client-side AI to hand-roll provider crawling.
- Still closed: no live Notion fetch adapter, OAuth, provider API calls,
  credential value reads, title/body reads, media downloads, fixture writes,
  zettel writes, edge writes, receipts, or object manifest updates.

## v0.3.130 - 2026-06-22

- Added read-only
  `archive notion-ancestor-fetch-adapter-execution-contract --dry-run` and MCP
  `notion_ancestor_fetch_adapter_execution_contract`.
- The contract reuses the scoped ancestor crawl request planner, reports
  credential ref presence without echoing exact refs, defines the future
  adapter input queue contract, requires a sanitized
  `notion_ancestor_result_fixture` output, and routes the next local step to
  `notion-ancestor-merge-plan`.
- Still closed: no live Notion fetch adapter, OAuth, provider API calls,
  credential value reads, title/body reads, media downloads, fixture writes,
  zettel writes, edge writes, receipts, or object manifest updates.

## v0.3.129 - 2026-06-22

- Added optional request-queue scope filters to read-only
  `archive notion-ancestor-crawl-plan --dry-run` and MCP
  `notion_ancestor_crawl_plan`.
- The planner can now narrow broad workspace crawl queues by generation id,
  root/ref, exact ancestor ref, or affected leaf ref before any future
  credential-bounded adapter receives the queue.
- Each crawl request now carries safe affected generation ids, affected root
  refs, and lineage refs so adapter input packages can be audited without page
  titles, bodies, comments, media, provider URLs, local paths, account ids,
  emails, tokens, or secret values.
- Still closed: no live Notion fetch adapter, OAuth, provider API calls,
  title/body reads, media downloads, fixture writes, zettel writes, edge writes,
  receipts, or object manifest updates.

## v0.3.128 - 2026-06-22

- Added read-only `archive notion-client-fixture-request-plan --dry-run` and
  MCP `notion_client_fixture_request_plan` to package the minimal sanitized
  fixture request contract for client Notion nested-tree verification.
- The request package lists accepted fixture kinds, required safe fields,
  redaction rules, and next verification commands; when preview fixtures are
  supplied it reuses `notion-client-issue-verification-plan` to decide the next
  requested fixture.
- Added documentation, capability matrix coverage, public documentation map
  links, release notes, CLI tests, MCP tests, and AI guide routing for the
  client fixture request command.
- Still closed: no client message sending, live Notion transport, OAuth,
  provider API calls, title/body reads, media downloads, fixture writes, zettel
  writes, edge writes, receipts, or object manifest updates.

## v0.3.127 - 2026-06-22

- Added read-only `archive notion-client-issue-verification-plan --dry-run`
  and MCP `notion_client_issue_verification_plan` to verify a client Notion
  nested-tree issue from sanitized local fixture bundles.
- The verifier orchestrates sanitized nested tree planning, optional reviewed
  block mirror preview, missing ancestor crawl request packaging, and optional
  sanitized ancestor merge/replan into one verdict-oriented `plan_state`.
- Added documentation, capability matrix coverage, public documentation map
  links, release notes, CLI tests, MCP tests, and AI guide routing for the
  client issue verification command.
- Still closed: no live Notion transport, OAuth, provider API calls, title/body
  reads, media downloads, fixture writes, zettel writes, edge writes, receipts,
  or object manifest updates.

## v0.3.126 - 2026-06-22

- Added read-only `archive notion-block-mirror-tree-fixture-plan --dry-run`
  and MCP `notion_block_mirror_tree_fixture_plan` to turn reviewed Notion block
  mirror metadata into a sanitized nested-tree fixture preview and immediate
  nested-tree plan preview.
- Added read-only `archive notion-ancestor-merge-plan --dry-run` and MCP
  `notion_ancestor_merge_plan` to merge sanitized ancestor result nodes into a
  nested-tree fixture preview and re-run the nested tree planner in memory.
- Added fake archive sample fixtures, CLI/MCP tests, capability matrix docs, AI
  routing hints, README summaries, and release notes while keeping the loop
  local and read-only: no provider calls, OAuth, page titles, page bodies,
  media downloads, fixture writes, zettel writes, edge writes, receipts, or
  object manifest updates.

## v0.3.125 - 2026-06-22

- Added read-only `archive notion-ancestor-crawl-plan --dry-run` and MCP
  `notion_ancestor_crawl_plan` to package missing Notion ancestor refs from the
  nested tree hold queue into a `crawl_request_queue` for a future
  credential-bounded adapter.
- Hardened `archive notion-nested-tree-plan --dry-run`: `content_class` can now
  be derived from `node_kind`, structural-node/content conflicts route to human
  review, duplicate `generation_id` values are allowed across unique roots,
  `source_status=trashed` normalizes to `trash`, prefix-like ref mismatch
  warnings are surfaced, and oversized fixtures block instead of returning
  partial success.
- Updated CLI/MCP tests, capability matrix docs, AI routing hints, README
  summaries, and release notes while keeping the surface read-only: no provider
  calls, real exports, page titles, page bodies, media downloads, zettel writes,
  edge writes, receipts, fixture merges, or object manifest updates.

## v0.3.124 - 2026-06-21

- Added read-only `archive notion-nested-tree-plan --dry-run` and MCP
  `notion_nested_tree_plan` for sanitized Notion nested tree fixtures.
- The planner walks safe parent refs from leaf pages to reviewed generation
  roots, separates live content leaves from structure/template/view-container
  nodes, and reports untraceable parent chains instead of guessing from a
  partial local mirror.
- Added fake archive fixture coverage, CLI/MCP tests, capability matrix docs,
  and release notes while keeping the surface fixture-only: no real exports,
  page titles, page bodies, provider calls, minting, zettel writes, edge writes,
  receipts, or object manifest updates.

## v0.3.123 - 2026-06-21

- Added dedicated `contains` link type definitions to the base and fake archive
  `zettel-kasten/types.yml` files for structural child page, child database,
  collection view, or nested archive containment.
- Extended Notion connection planning, the parser contract, sanitized fixture
  parsing, and connection edge intelligence with `notion_containment` evidence
  that maps to `contains`.
- Added a model-gap escalation guard so AI runtimes and future parsers should
  stop and report developer decision required instead of silently coercing
  containment into `view_query`, `references`, `material`, or `inherited_by`.
- Updated `ai-response-concept-guide`, the capability matrix, README summaries,
  and CLI/doc tests so beginner-facing explanations name containment as a
  structural relation without adding provider reads or durable edge writes.

## v0.3.122 - 2026-06-21

- Added `archive ai-usage-plan --dry-run` to estimate explicit archive-relative
  UTF-8 context files against a token budget without echoing file contents.
- Added approval-gated `archive ai-usage-record --dry-run|--approve` for
  non-secret AI runtime token usage receipts under `receipts/ai-usage/`.
  Receipts record task id, runtime, model, purpose, input/output/total tokens,
  optional cached/reasoning counters, and optional budget/planned-token metadata.
- Added read-only `archive ai-usage-report --dry-run` to aggregate local AI
  usage receipts by runtime, model, and purpose without reading prompts,
  responses, source object bytes, provider APIs, secrets, or local absolute
  paths.
- Kept this as an observability baseline, not live LLM provider integration:
  WOM-kit does not call model APIs, retrieve provider usage, price requests,
  store prompts, store responses, or enforce hard runtime budgets in this
  release.

## v0.3.121 - 2026-06-21

- Added scoped archive validation with `archive validate --since
  <batch-id-or-receipt>` for mint, retired-draft, and zettel-edge batch
  receipts, so operators can recheck only the artifacts touched by a recent
  approved batch instead of always starting with a full archive pass.
- Added indexed facet validation with repeated `archive validate --scope
  <facet=value>` filters. The command requires a current generated index and
  validates only the matching zettels plus the narrow global structure checks
  needed to interpret them safely.
- Added generated-index zettel cache columns for `file_size`,
  `file_mtime_ns`, `body_sha256`, `approved_body_sha256`, and
  `forbidden_location_reference_found`, allowing scoped validation to reuse
  unchanged indexed frontmatter/body evidence instead of rereading every
  selected body.
- Added `archive validate --progress` output on stderr with stage/item counts,
  elapsed time, and ETA for long scoped or full validation runs.
- Kept scoped validation explicitly narrower than full validation: it does not
  replace periodic `archive validate`, perform archive migration, call
  providers, or echo zettel body text.

## v0.3.120 - 2026-06-20

- Added a source-zettel-path edge receipt index for mint/retire target SHA
  evolution checks, so `retire-draft-batch` and `validate` no longer need to
  rescan `receipts/edges/*.zettel-edge.json` once per evolved target.
- Changed `retire-draft-batch` so approve mode reuses the successful per-item
  retirement plan and performs O(1) current-file SHA replay checks before
  deleting a draft and writing its retired-draft receipt, instead of rebuilding
  the same retirement plan a second time per item.
- Updated `validate` / `doctor` target SHA evolution checks to use a lazy
  Doctor-level edge receipt cache. Multiple mint and retired-draft receipts that
  point at post-edge canonical zets share the same cache.
- Added regression coverage proving edge-evolved `retire-draft-batch` and
  `validate` do not fall back to per-item edge receipt scans.

## v0.3.119 - 2026-06-20

- Added `archive mint-zet-batch --plan <json> --dry-run|--approve`, with
  aliases `mint-zettel-batch`, `bulk-mint`, and `bulk-mint-zet`, so many draft
  zets can be minted from one reviewed plan inside one WOM-kit process.
- Added `archive retire-draft-batch --plan <json> --dry-run|--approve`, with
  aliases `retire-minted-draft-batch`, `bulk-retire`, and
  `bulk-retire-draft`, so many already minted inbox drafts can be retired
  without per-item shell process loops.
- Added batch-level idempotency controls: `--skip-existing`, `--max-items`,
  per-item failure lists, sanitized per-item summaries, and one batch receipt
  under `receipts/mint/batches/` or
  `receipts/mint/retired-drafts/batches/`.
- Documented `--dry-run --skip-existing` as the single-process status/query
  path for large mint or retire plans, so operators do not need `find | xargs`
  counting loops to identify already processed items.
- Kept the existing single-item mint and retire gates underneath the batch
  commands. A batch item still needs the same dry-run evidence, human
  `--reviewed-by` approval on write, SHA/path checks, duplicate checks, and
  receipt evidence as the single-item commands.
- Added CLI regression tests for dry-run, approve, alias routing,
  `--skip-existing`, batch receipts, no body text echo, no absolute local path
  echo, and no per-item shell process spawning.

## v0.3.118 - 2026-06-20

- Added generated-index metadata for canonical zettel count and max mtime during
  `archive index`, stored in `index_metadata` inside `db/archive-index.sqlite`.
- Changed generated-index-backed `mint-zet` duplicate checks so current-format
  indexes use metadata for staleness validation instead of globbing and statting
  every canonical zettel before each mint.
- Kept compatibility for older generated indexes: if `index_metadata` is missing
  or malformed, mint falls back to the legacy live staleness scan instead of
  trusting the index blindly.
- Updated approved mint index upserts so large mint batches keep both the new
  canonical row and index metadata current after each approved mint.
- Added SQLite generated-index contention hardening: WOM-kit now opens archive
  index connections with a 30s `busy_timeout`, uses WAL mode on index write
  paths, and treats SQLite WAL/SHM/journal sidecars as rebuildable generated
  archive artifacts.
- Added regression coverage proving standard-id mint does not call
  `iter_zettel_paths` or `safe_archive_glob` when the current generated-index
  fast path is available.

## v0.3.117 - 2026-06-20

- Added AI operational context rehydration through `ops/operational-context.yml`
  and runtime-context field `operational_context`, so an AI runtime can recover
  mission, scope, state, gotchas, reviewed decisions, and next actions before
  broad archive reads after context compression or session reset.
- Added CLI `archive operational-context <archive-root> --dry-run --format json`
  for read-only inspection and candidate validation, plus approval-gated
  `--record ... --approve --reviewed-by <actor>` writes that replace the record
  and write `receipts/operational-context/*.operational-context.json`.
- Added privacy guards that block provider URLs, local path hints, email-like
  account labels, tokens, and secret-like values in operational-context candidate
  values before any write.
- Updated runtime canonical entrypoint order, capability matrix, README, fake
  archive fixture, and docs so public readers can see that this is a bounded AI
  rehydration layer, not broad archive scanning, provider sync, MCP write
  behavior, or a replacement for zets and receipts.

## v0.3.116 - 2026-06-19

- Added a standard zettel-id source path fast path to `resolve_zettel_path`:
  when standard `inbox/<zettel_id>.md` or `zettels/<zettel_id>.md` exists and its
  frontmatter id matches, WOM-kit resolves that file directly before falling
  back to the legacy archive-wide id scan.
- Closed the remaining mint scale gap after v0.3.114: `archive mint-zet
  --zettel-id ... --dry-run|--approve` no longer reparses every zettel just to
  find a standard inbox draft path.
- Preserved compatibility for legacy non-standard filenames: if the direct file
  does not exist or its frontmatter id does not match, the existing full scan
  fallback still applies.
- Added a regression test that makes archive-wide id scanning fail during
  generated-index-backed mint dry-run and approve flows, proving the standard
  path is used.

## v0.3.115 - 2026-06-19

- Added a public WOM product roadmap that explains the intended pre-1.0 phase
  meaning: `v0.1.x` idea/protocol language, `v0.2.x` local implementation,
  `v0.3.x` WOM real-use feedback and safety hardening, `v0.4.x` custom UI
  control layer, and `v0.5.x` ZET real-use feedback.
- Linked the roadmap from the top-level README, public documentation map,
  capability matrix, and release notes so public readers can understand the
  release line without inferring the plan from individual changelog entries.
- Kept the change documentation-only: no new product command, UI behavior, live
  provider adapter, ZET transport, wallet, token, sync, or background worker was
  added.

## v0.3.114 - 2026-06-19

- Optimized mint duplicate checks for large archives: when
  `db/archive-index.sqlite` is current, `archive mint-zet --dry-run|--approve`
  compares canonical zettel id/title/body-start data through the generated index
  instead of rereading every canonical zet body on every mint.
- Kept large mint loops on the fast path by upserting the newly minted canonical
  row into the generated index after an approved mint that used a current index;
  missing or stale indexes still fall back to the existing live scan without
  changing duplicate semantics.
- Applied the approved post-receipt edge-only target SHA exemption to
  `retire-draft`, so a draft can retire after minting even when reviewed
  zettel-edge writes have grown the canonical zet frontmatter.
- Shared the edge-only target SHA reconstruction helper between `retire-draft`
  and `doctor` / `validate`, keeping body edits and non-edge frontmatter drift
  blocked.

## v0.3.113 - 2026-06-19

- Added `account_recovery_codes` and `break_glass_secrets` to
  `credential-store-recommendation`, with KeePassXC-style `secret:` guidance,
  required independent offline redundancy, a two-location minimum, and an
  explicit circular-dependency check for vault/account recovery loops.
- Extended the credential semantic extraction recipe so `recovery_codes` route
  toward the account recovery scenario and wallet seed/private-key material
  routes toward the break-glass scenario without reading plaintext files or
  returning secret values.
- Documented the break-glass boundary for 2FA recovery codes and emergency-only
  secrets: WOM stores refs, safe labels, and redundancy metadata only, never the
  recovery code values.

## v0.3.112 - 2026-06-19

- Fixed mint and retired-draft receipt validation after normal graph growth:
  `archive validate` / `archive doctor` now accept historical target SHA-256
  values when the current canonical zet can be reconstructed by removing only
  approved post-receipt `zettel-edge` writes.
- Preserved draft snapshot bytes during minting so LF-only source drafts no
  longer become CRLF snapshots on Windows, while canonical zet generation keeps
  the existing normalized text path.
- Allowed `retire-draft` to close legacy minted draft pairs whose source and
  snapshot hashes differ only by LF/CRLF newline normalization, with a warning
  instead of a blocker.
- Fixed the remaining `zettel-edge-batch` scale hang path for zet-to-zet rows by
  preloading one zettel id/path index for policy-writable batch items, matching
  the earlier object-manifest index optimization for objet targets.
- Kept the boundary local and receipt-gated: no receipt rewriting, edge
  re-sealing command, provider calls, source export reads, object byte reads,
  automatic edge inference, or unreceipted integrity bypass was added.

## v0.3.111 - 2026-06-18

- Fixed the `object_id_only` / forbidden-location guard so escaped LaTeX
  commands such as `\\frac` and `\\sigma_Y` are no longer treated as Windows
  UNC path references, while real UNC/local absolute paths remain blocked.
- Expanded `archive import-external` manifest fidelity for structured Notion
  migration: safe zettel id overrides, safe arbitrary facets, and safe
  non-object `source_refs` are preserved into imported draft frontmatter.
- Added `archive import-external --provider-locator-policy object-ref`, which
  converts supported Notion body locators to one reviewed `objet:<object_id>`
  reference when the manifest has exactly one safe object source ref.
- Aligned import and mint safety gates by blocking imported bodies that would
  leave provider URLs or local paths in draft text; dry-run still reports counts
  and actions without echoing object ids or provider locator values.
- Kept the boundary local and approval-gated: no provider calls, OAuth flows,
  source export reads beyond the selected local import item, object byte reads,
  edge writes, body rewrites outside approved import drafts, or custom live
  importer adapters were added.

## v0.3.110 - 2026-06-18

- Added `archive retire-draft --dry-run|--approve` for closing an already
  minted inbox draft only after the canonical zet, mint receipt, draft
  snapshot, archive-relative paths, and SHA-256 evidence all agree.
- Approved retirement removes the verified inbox draft and writes a schema-backed
  receipt under `receipts/mint/retired-drafts/`, while preserving the canonical
  zet, original mint receipt, and draft snapshot.
- `archive validate` / `archive doctor` now classify a still-present inbox draft
  backed by complete mint artifacts as an informational cleanup candidate rather
  than a mint metadata error, and accept a retired mint source when the retire
  receipt proves that lifecycle closure.
- The mint checklist title gate is CJK-width aware, so short meaningful Korean,
  Japanese, or Chinese titles can pass while generic placeholders remain
  blocked.
- Near-duplicate warnings no longer trigger on title alone when the body is
  materially different; `same_title` remains a warning when the body start is
  also very similar.
- Kept the boundary local and evidence-gated: no provider calls, source export
  reads, object byte reads, canonical zet deletion, mint receipt deletion, or
  unverified inbox cleanup were added.

## v0.3.109 - 2026-06-18

- Added receipt-backed `archive migrate --target link-types-v0.3 --revert
  --dry-run|--approve` for safe link-type migration rollback.
- The link-type revert removes only recommended connection edge vocabulary
  records that the migration receipt lists as appended, are unused by current
  zettel edges, and are unchanged from the base WOM-kit type template.
- Forward `link-types-v0.3` approval now writes a migration receipt under
  `receipts/migrations/`; approved revert writes a matching receipt under
  `receipts/migrations/reverts/`.
- The revert blocks if a candidate link type is already used by a zettel edge or
  has been locally modified, avoiding accidental vocabulary loss after real
  graph writes.
- Added explicit `frontmatter-v0.3 --revert` fail-closed behavior with
  `snapshot_receipt_required`, because lossless frontmatter rollback needs
  future migration snapshot receipts.
- Kept the boundary local: no provider calls, source export reads, edge writes,
  edge receipt deletion, unreceipted type removal, or guessed frontmatter
  restoration were added.

## v0.3.108 - 2026-06-18

- Fixed the matching large-manifest scale issue in `archive zettel-edge-batch`
  when policy-writable rows target manifested objets.
- Batch edge preflight and approval now preload `objects/manifests/files.jsonl`
  once and reuse a local object-id index instead of resolving each objet target
  through repeated full manifest scans.
- Added receipt-based rollback commands:
  `archive revert-edge --receipt <edge-receipt> --dry-run|--approve` and
  `archive revert-batch --receipt <batch-receipt> --dry-run|--approve`.
- Reverts preserve the original write receipts, write new revert receipts under
  `receipts/edges/reverts/` and `receipts/edges/batches/reverts/`, and restore
  touched files if an approved batch revert fails partway through.
- Added regression coverage for object-target batch manifest preloading and
  batch receipt rollback.
- Kept the boundary local and approval-gated: no provider calls, MCP write
  tools, source export reads, zettel body echoes, object manifest updates, or
  original receipt deletion were added.

## v0.3.107 - 2026-06-18

- Fixed the large-manifest startup hang in
  `archive notion-objet-source-map-link-plan` and the dependent
  `archive notion-objet-import-clue-audit` path.
- Reused one preloaded object-manifest index for source-map material planning
  instead of resolving each manifest object through a full manifest reload, and
  kept local candidate checks lightweight for archive-relative paths.
- Added a regression test that blocks per-object `resolve_objet_ref` calls on a
  scaled manifest fixture.
- Verified the fix against a real large local archive shape with 19k object
  manifest rows, 303 zettel sources, and 121/120 source-map/ledger rows: the
  source-map planner and import clue audit complete in seconds instead of
  timing out with zero output.
- Kept the commands read-only: no zettel body reads, object byte reads, provider
  calls, provider URL echoes, edge writes, receipt writes, or body rewrites were
  added.

## v0.3.106 - 2026-06-17

- Added machine-readable AI guide handoff fields to `runtime-context`
  `canonical_entrypoints`: `ai_runtime_order`, `recommended_first_commands`,
  and `material_link_routes`.
- The handoff tells terminal-capable AI runtimes to run `runtime-context`, read
  canonical entrypoints and `AGENTS.md`, then run
  `ai-response-concept-guide` before choosing Notion material-link routes.
- Kept the surface read-only: it reads no file bodies, writes nothing, calls no
  providers, reads no secrets, and only returns archive-relative commands and
  safe routing labels.

## v0.3.105 - 2026-06-17

- Updated approved `archive import-external` writes so a manifest item with an
  explicit safe `object_id`, `objet_ref`, or object-valued `source_refs` entry
  preserves that clue in the imported draft zettel's `source_refs`.
- Added dry-run `source_ref_count` / `source_refs_preserved` preview fields so
  operators can see that a safe material clue will be kept without echoing the
  object id in the dry-run batch output.
- Kept the preservation narrow: it does not treat the imported text body hash as
  a source object id, does not preserve provider URLs as object refs, does not
  read object bytes, call providers, upload files, write edges, or create
  receipts beyond the existing approved external-import receipt.

## v0.3.104 - 2026-06-17

- Added read-only CLI `archive notion-objet-import-clue-audit <archive-root>
  --source-map <archive-relative-jsonl> --ledger <archive-relative-jsonl>
  --dry-run` and MCP `notion_objet_import_clue_audit`.
- The audit checks imported Notion zettels whose provider locators may have
  been omitted from bodies, then classifies each zettel as having a preserved
  object ref/edge, a source-map join candidate, a missing material clue after
  locator omission, or no omission signal.
- Updated `ai-response-concept-guide` routing so AI runtimes can audit import
  clue preservation before deciding between source-map linking and older
  body-locator tools.
- Kept the feature local and bounded: no zettel body reads, provider calls,
  object byte reads, body rewrites, edge writes, receipt writes, provider URL
  echoes, page title echoes, frontmatter value echoes, account ids, emails,
  tokens, or secret values were added.

## v0.3.103 - 2026-06-17

- Added read-only CLI `archive notion-objet-source-map-link-plan <archive-root>
  --source-map <archive-relative-jsonl> --ledger <archive-relative-jsonl>
  --dry-run` and MCP `notion_objet_source_map_link_plan` for planning
  zet-to-objet material-link candidates after provider locators have already
  been removed from imported zettel bodies.
- The planner joins source maps, optional download/retrieval ledgers, zettel
  frontmatter metadata, and `objects/manifests/files.jsonl` rows by
  private-value fingerprints, then returns candidate `embed` edges with
  `candidate_id`, `join_basis`, `write_status`, and
  `human_review_required`.
- Updated AI runtime routing docs so `runtime-context` and
  `ai-response-concept-guide` point agents to the source-map material bridge
  before falling back to body-locator based Notion objet link tools.
- Kept the feature local and bounded: no provider calls, object byte reads,
  zettel body reads, body rewrites, edge writes, receipt writes, presigned URLs,
  source value echoes, local path echoes, account ids, emails, tokens, or secret
  values were added.

## v0.3.102 - 2026-06-17

- Extended read-only CLI `archive ai-response-concept-guide <archive-root>
  --topic all|operational_terms --locale ko-KR|en-US --dry-run` with an
  operational terminology translation layer for edge types, lifecycle terms,
  and connection kinds.
- Added a sanitized version-chain heuristic to
  `connection-edge-intelligence-plan` so reviewed metadata hints can recommend
  the existing `supersedes` / `version_replacement` meaning without reading
  source bodies or writing edges.
- Improved `archive zettel-edge-batch`: `--plan workbench/...` now resolves
  archive-relative first with a safe missing-path hint, and explicit
  `--skip-existing` separates already-written rows into `skipped_existing_edges`
  so the rest of a reviewed batch can continue.
- Kept the feature local and bounded: no provider calls, OAuth, real export
  parsing, source body reads, derived-text body reads, LLM classification,
  candidate record writes, MCP write tools, or secret/local-path/provider URL
  echoing were added.

## v0.3.101 - 2026-06-17

- Added approval-gated CLI `archive notion-objet-link-convert <archive-root>
  --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex>
  --object-id sha256:<hex> --target-mode embed_edge
  --expected-occurrence-count <n> --dry-run|--approve`.
- The command re-runs `notion-objet-link-rewrite-plan`, requires
  `--expected-occurrence-count` for approved writes, then routes the reviewed
  object link through the existing single `zettel-edge` gate as one `embed`
  edge.
- Approved writes add one source zettel frontmatter edge, one normal
  `receipts/edges/*.zettel-edge.json` receipt, and one
  `receipts/objects/notion-link-conversions/*.notion-objet-link-convert.json`
  conversion receipt, with rollback snapshots for touched paths.
- Kept body rewrite closed: `target_mode=objet_ref_rewrite` remains blocked,
  MCP exposes no write tool, and the command calls no providers, reads no
  object bytes or real exports, rewrites no provider locator text, and echoes
  no provider URLs, locator text, zettel body text, zettel titles, frontmatter
  values, page titles, credentials, or secrets.

## v0.3.100 - 2026-06-17

- Added approval-gated CLI `archive notion-objet-manifest-locator-label
  <archive-root> --object-id sha256:<hex> --locator-fingerprint sha256:<hex>
  --dry-run|--approve` with alias `archive notion-objet-locator-label`.
- The command writes one reviewed, non-secret Notion locator fingerprint to one
  existing `objects/manifests/files.jsonl` object record, plus a receipt under
  `receipts/objects/notion-locator-labels/`.
- This lets `notion-objet-link-index` and `notion-objet-link-plan` match a
  zettel locator to a manifested objet when the manifest knows it came from a
  Notion export but did not preserve the locator fingerprint.
- Kept raw provider locator text closed: the command reads no zettel bodies or
  object bytes, rewrites no zettels, writes no edges, calls no providers,
  exposes no MCP write tool, and echoes no provider URLs, provider locator
  text, zettel body text, zettel titles, credentials, or secrets.

## v0.3.99 - 2026-06-17

- Added approval-gated CLI `archive zettel-edge-batch <archive-root>
  --plan <json> --dry-run|--approve` with aliases `archive bulk-zettel-edge`
  and `archive batch-zettel-edge`.
- The batch writer reads a reviewed JSON policy plan, routes only policy-
  matching high-confidence rows through the existing single-edge
  `zettel-edge` preflight/write gate, and leaves ambiguous, low-confidence, or
  policy-mismatched rows in `human_review_queue`.
- Approved batches write individual `receipts/edges/*.zettel-edge.json`
  receipts plus one `receipts/edges/batches/*.zettel-edge-batch.json` receipt,
  and restore touched zettel/receipt files if a batch write fails partway.
- Kept the feature CLI-only and bounded: it does not parse real exports, call
  providers, start OAuth, open Notion, call an LLM, write candidate records,
  update object manifests, expose an MCP write tool, or echo zettel body text,
  zettel titles, provider URLs, local paths, credentials, or secrets.

## v0.3.98 - 2026-06-17

- Added read-only `archive notion-objet-link-rewrite-plan <archive-root>
  --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex>
  --object-id sha256:<hex> --dry-run` and MCP
  `notion_objet_link_rewrite_plan`.
- The new planner validates one human-reviewed Notion locator/object pair after
  `notion-objet-link-plan`: selected locator fingerprint, selected object id,
  target mode, and optional occurrence-count drift guard.
- Output includes safe selected locator metadata, selected manifest candidate
  metadata, an approval checklist, and `would_change` for the future approved
  conversion shape.
- Kept the feature read-only: it writes no zettels, rewrites no provider
  locators, writes no `embed` edges, reads no object bytes, calls no providers,
  creates no presigned URLs, and echoes no provider URLs, zettel body text,
  frontmatter values, page titles, absolute local paths, credentials, or
  secrets.

## v0.3.97 - 2026-06-17

- Added read-only `archive view-recommendation-plan <archive-root> --dry-run`
  and MCP `view_recommendation_plan`.
- The new planner reuses `view-health` facet role diagnostics to propose
  candidate single-facet saved views from likely navigation axes and actual
  indexed top values.
- Recommendations include suggested `view.ai.<axis>.<value>` ids,
  `facets.<key>` filters, match counts, and whether a key/value pair is already
  used by an existing saved view filter.
- Kept the feature read-only: it writes no `views/*.yml`, rebuilds no index,
  rewrites no zettel facets, reads no zettel bodies or object bytes, calls no
  providers, and echoes no zettel titles, absolute local paths, provider URLs,
  credentials, or secrets.

## v0.3.96 - 2026-06-17

- Added read-only `archive notion-objet-link-index <archive-root> --dry-run`
  and MCP `notion_objet_link_index`.
- The new index scans non-redacted zets across an archive for Notion provider
  locator fingerprints, then reports safe counts for zets, locator rows,
  distinct locator fingerprints, and locator rows with or without manifested
  objet candidates.
- Output includes safe zettel summaries, object ids, and suggested
  `objet:sha256:<hex>` refs for later human review, but never echoes provider
  URLs, zettel body text, frontmatter values, page titles, absolute local paths,
  credentials, or secrets.
- The existing one-zettel `notion-objet-link-plan` remains the next review step
  before any future approval-gated locator rewrite or reviewed `embed` edge.
- Kept the feature read-only: it writes no zettels, writes no edges, calls no
  providers, creates no presigned URLs, reads no object bytes, and skips
  redacted zettel content.

## v0.3.95 - 2026-06-17

- Added `mint_checklist_guidance` to read-only `archive mint-zettel --dry-run`
  / `archive mint-zet --dry-run` output.
- The guidance reports missing required checklist ids, checklist items that
  need explicit human review, the preferred `mint.checklist` frontmatter path,
  the legacy accepted `promotion.checklist` path, and a safe boolean-only
  frontmatter example.
- Text output now prints checklist guidance when required mint checklist items
  are missing.
- Updated the beginner quickstart to explain that items such as
  `one_clear_purpose` and `sensitive_content_reviewed` should only be marked
  true after the human reads the draft.
- Kept minting approval rules unchanged: dry-run writes nothing, real minting
  still requires `--approve` and `--reviewed-by`, and machine-enforced safety
  checks still run at mint time.

## v0.3.94 - 2026-06-17

- Improved read-only `archive projection-plan --dry-run` surface guidance.
- CLI help now lists supported projection surface kinds and projection formats
  instead of requiring users to infer them from source code.
- Blocked JSON output now includes `projection_contract` with supported
  surface kinds, surface prototype kinds, visibility values, and projection
  formats, plus safe `surface.requested_surface_kind` and `surface_status`.
- Unsupported surface values no longer prevent a safe zet reference from being
  resolved, so blocked output can still show safe zet metadata instead of
  nulling the whole plan context.
- Invalid `--surface notion` now explains that Notion belongs to the separate
  `zet-surface-prototype --surface-kind notion` preview rather than the
  projection-plan surface set.
- Kept the command read-only: it renders no body output, writes no projection
  records or receipts, calls no providers, publishes nothing, runs no ZET
  transport, and echoes no unsafe raw surface URLs, local paths, credentials, or
  secret values.

## v0.3.93 - 2026-06-17

- Extended read-only `archive view-health <archive-root> --dry-run` and MCP
  `view_health` with `facet_role_summary` and `facet_roles`.
- The new output uses static key heuristics to separate likely navigation axes
  such as `subject`, `institution`, `record_type`, and `source_category` from
  internal/import metadata such as `notion_status`, `migration_batch`, and
  `contents`.
- Text output now prints navigation/internal/unknown facet key counts so AI
  navigation view repair can start from visible facet roles instead of one
  noisy mixed table.
- Kept the feature read-only: it writes no view files, rewrites no zettel
  facets, rebuilds no index, reads no zettel bodies or object bytes, calls no
  providers, and echoes no zettel titles, absolute local paths, provider URLs,
  account ids, emails, tokens, or secret values.

## v0.3.92 - 2026-06-17

- Added `review_summary` output to read-only
  `archive connection-edge-intelligence-plan --dry-run`, separating
  `ambiguous_count` from candidate-level `human_review_required_count` and
  durable-write approval counts.
- The text output now prints human-review-required candidate counts,
  durable-write approval counts, and `auto_writable_count: 0` so
  `ambiguous_count: 0` cannot be mistaken for "ready to write".
- Expanded the human review queue entries with ambiguity and parsimony signals
  while keeping candidate ids opaque.
- Kept the command read-only and privacy-bounded: it writes no candidate
  records, zets, edges, receipts, or manifests; calls no providers or LLMs; and
  echoes no body text, provider URLs, local paths, account ids, emails, tokens,
  or secret values.

## v0.3.91 - 2026-06-17

- Added read-only CLI `archive index-health <archive-root> --dry-run` and MCP
  `index_health` to check generated-index drift before running `view-zets`,
  `view-health`, `related-zets`, or `search`.
- The check compares live zettel paths and basic frontmatter metadata
  (`id`, `status`, and `kind`) against rows in `db/archive-index.sqlite`, and
  flags zettel files modified after the index was generated.
- Output reports missing live zets, extra indexed paths, changed metadata, and
  modified-after-index samples with archive-relative paths only.
- Kept the command read-only: it writes nothing, rebuilds no index, reads no
  object bytes, calls no providers, and echoes no zettel body text, zettel
  titles, absolute local paths, provider URLs, account ids, emails, tokens, or
  secret values.

## v0.3.90 - 2026-06-17

- Added read-only CLI `archive view-health <archive-root> --dry-run` and MCP
  `view_health` to diagnose saved view drift before editing `views/*.yml`.
- The health check reads the generated local index and reports saved view
  counts by `active`, `empty_result`, and `blocked`, plus per-filter facet
  diagnostics and observed facet value samples for keys used by saved views.
- This helps real archives discover why default or imported AI navigation views
  return zero zets when saved filters such as `facets.domain` no longer match
  the actual facet distribution.
- Kept the command read-only: it writes nothing, reads no zettel bodies, echoes
  no zettel titles, absolute local paths, provider URLs, account ids, emails,
  tokens, or secret values, calls no providers, and reads no object bytes.

## v0.3.89 - 2026-06-17

- Added read-only CLI `archive notion-objet-link-plan --path <zet.md>|--zettel-id
  <id> --dry-run` and MCP `notion_objet_link_plan` for the Phase 3 gap where
  imported zet bodies contain Notion provider locators instead of
  `sha256:<hex>` or `objet:sha256:<hex>` refs.
- The planner scans one non-redacted zettel for Notion provider locators,
  groups them by opaque `sha256:` locator fingerprint, and matches them against
  existing `objects/manifests/files.jsonl` records when the manifest carries an
  exact redacted locator field or reviewed locator fingerprint.
- Candidate output surfaces only safe manifest object ids, match field names,
  store labels, and resolver states, so a reviewed operator can replace the
  locator with `objet:sha256:<hex>` or write a reviewed embed edge later.
- Kept the new path read-only and privacy-bounded: it writes nothing, calls no
  providers, starts no OAuth, creates no provider or presigned URLs, reads no
  object bytes, and echoes no zettel body text, frontmatter values, provider
  URLs, page titles, local paths, account ids, emails, tokens, or secret values.

## v0.3.88 - 2026-06-17

- Added overview-first zet reading through `archive read-zettel --section
  overview`, returning a cheap first-read card with gist, facets, tie counts,
  and edge previews while omitting the full body and full frontmatter details.
- Added `first_read` to `archive block-header --dry-run` output so AI runtimes
  can inspect a zet's short meaning signal and tie summary before reading the
  full body. The first-read card stays outside `header_preview`, so existing
  header hash boundaries are not redefined.
- Added approval-gated `archive migrate --target link-types-v0.3` to append
  missing recommended connection edge vocabulary from the base
  `zettel-kasten/types.yml` into stale archive-local `types.yml` files.
- Extended `archive zettel-edge` target resolution so safe external refs such
  as `zet:notion:ZET637` can resolve to archive-local zet ids such as
  `zet_notion_db3_ZET0637` before the edge preview/write.
- Hardened mint and draft safety checks so plain `https://` provider URLs in
  zet bodies, including Notion page mentions, block `object_id_only` even when
  legacy frontmatter checklist values claimed the item was already passed.
- Kept the new paths local and privacy-bounded: they call no providers, start
  no OAuth, read no source exports, read no object bytes, write no bulk edge
  candidates, expose no provider URLs, and do not implement Notion
  embed-to-objet sha256 conversion yet.

## v0.3.87 - 2026-06-17

- Added read-only CLI `archive connection-edge-intelligence-plan
  --evidence <archive-relative-json> --source notion --dry-run`, with alias
  `connection-edge-classification-plan`, for reviewing sanitized connection
  fixture candidates before durable edge writes.
- The plan separates source mechanism from relationship meaning, keeps current
  active edge types conservative, and surfaces provisional meaning labels such
  as `format_variant`, `responds_to`, `fulfills`, `enabling`, and `sequence`
  as review labels rather than active link types.
- Added ambiguity, parsimony, and human-review queue signals so vague
  `semantic` links can be named more specifically or dropped before
  `zettel-edge` writes.
- Kept the command read-only: it reads no real exports, source bodies,
  derived-text bodies, or comment bodies, calls no providers or LLMs, runs no
  multi-lens AI classifier, writes no candidates, zets, edges, receipts, or
  manifests, and echoes no provider URLs, local paths, page titles, comment
  bodies, source body text, derived-text body text, account ids, emails,
  tokens, or secret values.

## v0.3.86 - 2026-06-17

- Added read-only CLI `archive object-storage-upload-evidence-audit
  --receipt <archive-relative-json> --dry-run` for checking a v0.3.85 upload
  evidence receipt against `objects/manifests/files.jsonl`.
- The audit verifies receipt schema, lifecycle action, safe provider/store
  labels, non-secret privacy flags, closed no-provider actions, manifest update
  completion, linked `object_storage` locations, `declared_uploaded`
  availability, sha256 content-addressed key hints, and receipt/location count
  consistency.
- Kept the audit read-only: it writes no audit receipt, reads no source bytes,
  computes no local source hashes, calls no provider APIs, performs no remote
  HEAD checks, uploads/downloads/syncs nothing, creates no provider URLs, reads
  no secrets, and echoes no receipt path, manifest path, object ids, locations,
  provider URLs, bucket names, account ids, emails, tokens, or secret values.

## v0.3.85 - 2026-06-17

- Added approval-gated CLI `archive object-storage-upload-evidence
  --ledger <jsonl> --dry-run|--approve` for registering reviewed external
  object-storage upload evidence without provider calls.
- Dry-run mode reads UTF-8 JSONL upload evidence ledgers, counts successful
  `uploaded`, `verified`, `succeeded`, `already_present`, or `ok` rows, matches
  sha256 objects against `objects/manifests/files.jsonl`, previews manifest
  location updates, and echoes no ledger paths or row values.
- Approved mode requires `--reviewed-by` and a safe `--store-ref`, writes a
  non-secret receipt under
  `receipts/providers/object-storage-upload-evidence/`, and adds
  `object_storage` locations with `declared_uploaded` availability to existing
  object manifest records.
- Kept live provider work closed: no source bytes are read, no local hashes are
  computed, no R2/S3/API calls are made, no HEAD checks are performed, no
  upload/download/sync happens, no provider URLs or bucket names are created,
  and no secrets are read or echoed.

## v0.3.84 - 2026-06-17

- Added read-only CLI `archive ai-response-concept-guide --topic all
  --dry-run`, with aliases `ai-concept-guide` and `wom-concept-guide`.
- The command returns beginner-facing explanation cards for sha256 object
  identity vs location, object manifests vs zets, and the
  `objet -> derived text -> zet` layer split.
- Added structured safe routing hints and overclaim guardrails so an AI runtime
  does not claim upload, remote availability, provider URLs, or manifest proof
  without receipts.
- Kept the guide read-only: no source bytes, derived-text bodies, manifest
  writes, receipt writes, draft zets, minted zets, object uploads, provider
  calls, source filenames, local paths, provider URLs, account ids, emails,
  tokens, or secret values are produced.

## v0.3.83 - 2026-06-17

- Extended read-only `archive derive-text coverage --dry-run` and alias
  `archive derive-text-coverage --dry-run` with a `manifest_quality` block for
  existing `objects/manifests/derived-text.jsonl` records.
- The coverage gate now reports and blocks false complete claims when
  derived-text records are missing required extraction provenance such as
  `tool_version`, `tool_name`, `derivation_kind`, or `review_status`.
- `tool_version` values such as blank, `unknown`, `n/a`, `none`, `todo`, or
  `tbd` are treated as quality issues.
- Kept the workflow read-only: no source bytes, derived-text bodies, parser/OCR
  tools, provider APIs, receipts, derived text writes, zets, local paths, tool
  paths, provider URLs, tokens, or secret values are produced.

## v0.3.82 - 2026-06-17

- Added approval-gated CLI `archive zettel-edge --from-zettel <zet>
  --target <zet-or-objet> --edge-type <type> --dry-run|--approve`, with
  aliases `link-zettel-edge` and `write-zettel-edge`.
- The command writes exactly one reviewed edge to source zettel frontmatter and
  one non-secret receipt under `receipts/edges/*.zettel-edge.json`.
- Target validation is local and narrow: `zet_<id>` targets must resolve to an
  existing zettel, and `sha256:<64hex>` / `objet:sha256:<64hex>` targets must
  resolve through `objects/manifests/files.jsonl`.
- Duplicate `type + target` edges are blocked, `edge_type` must already be
  defined in `zettel-kasten/types.yml`, and MCP still exposes no write tool for
  this surface.
- Kept the workflow local and approval-gated: no Notion call, OAuth, real
  export read, comment read, media download, candidate record write, object
  manifest update, provider URL, local path, raw export path, page title,
  comment body, account id, email, token, or secret value is produced. The
  command does not echo zettel body text or zettel titles.

## v0.3.81 - 2026-06-16

- Added read-only `archive connection-evidence-parse-fixture --evidence
  <archive-relative-json> --source notion --dry-run`, aliases
  `connection-evidence-parser-fixture` and
  `notion-connection-evidence-parser-fixture`, and MCP
  `connection_evidence_parse_fixture`.
- Added fake archive fixture `workbench/connection-evidence.sample.json` so the
  parser path can be tested without real client exports.
- The fixture parser emits candidate edge previews for relation properties,
  synced block references, database view/filter snapshots, internal hyperlinks,
  page mentions, comment context, and objet embeds. It writes nothing and keeps
  real Notion export parsing unimplemented.
- Kept the workflow read-only: no Notion call, OAuth, real export read, comment
  read, media download, candidate record write, zet write, edge write, receipt
  write, object manifest update, provider URL, local path, raw export path, page
  title, comment body, account id, email, token, or secret value is produced.

## v0.3.80 - 2026-06-16

- Added read-only `archive connection-evidence-parser-contract --source
  notion --dry-run`, aliases `connection-parser-contract` and
  `notion-connection-parser-contract`, and MCP
  `connection_evidence_parser_contract`.
- Defined the future Notion connection evidence parser contract before real
  export parsing: accepted input lanes, candidate edge record fields, static
  snapshot requirements for dynamic view/filter and comment-context evidence,
  parser stages, and redaction rules.
- Kept the workflow read-only: no Notion call, OAuth, export read, comment read,
  media download, parser execution, candidate record write, zet write, edge
  write, receipt write, object manifest update, provider URL, local path, raw
  export path, page title, comment body, account id, email, token, or secret
  value is produced.

## v0.3.79 - 2026-06-16

- Added the recommended Notion connection edge vocabulary to the base
  `zettel-kasten/types.yml` and fake archive types:
  `material`, `derived`, `semantic`, `embed`, `mention`, `view_query`, and
  `comment_context`.
- Updated `connection-import-plan` so the current fake archive reports those
  recommended edge types as present instead of missing.
- Clarified that this is still a vocabulary/schema checkpoint before evidence
  parsing or edge writes: no Notion call, OAuth, export read, comment read,
  media download, zet write, edge write, receipt write, object manifest update,
  provider URL, local path, page title, comment body, account id, email, token,
  or secret value is produced.

## v0.3.78 - 2026-06-16

- Added read-only `archive object-storage-adapter-execution-contract
  --operation upload_object --dry-run`, aliases
  `object-storage-upload-execution-contract` and
  `objet-storage-adapter-execution-contract`, and MCP
  `object_storage_adapter_execution_contract`.
- The contract fixes the future upload adapter rules before live execution:
  sha256 content-addressed remote keys, approval receipt re-verification, local
  SHA-256 verification before upload, provider HEAD/idempotency checks, bounded
  retry/resume ledger, non-secret execution receipt, and manifest update only
  after provider confirmation.
- Clarified S3-compatible integrity handling: provider SHA-256 checksums are
  preferred when supported, and ETag is not treated as WOM SHA-256 unless a
  provider-specific policy verifies that equivalence for the exact upload mode.
- Kept the workflow read-only: no provider call, secret retrieval, object byte
  read, local hash computation, upload, remote availability check, resume ledger
  write, receipt write, manifest update, bucket name, prefix, provider URL,
  local absolute path, exact credential ref, token, or secret value is produced.

## v0.3.77 - 2026-06-16

- Added read-only `archive connection-import-plan --source notion --dry-run`
  and MCP `connection_import_plan` for Notion connection evidence.
- The planner maps relation properties, synced block references, database
  view/filter snapshots, internal links, page mentions, comment context, and
  objet embeds to typed-edge candidates.
- Added a recommended edge vocabulary for this feedback slice:
  `material`, `derived`, `semantic`, `embed`, `mention`, `view_query`, and
  `comment_context`.
- The planner checks the archive's allowed link types and reports which
  recommended edge types are missing before any write command exists.
- Kept the workflow read-only: no Notion call, OAuth, export read, comment
  read, media download, zet write, edge write, receipt write, object manifest
  update, provider URL, local path, page title, comment body, account id,
  email, token, or secret value is produced.

## v0.3.76 - 2026-06-16

- Added explicit `large_media_export_trap` output to
  `archive external-export-plan` so broad workspace/database exports that can
  pull uploaded files, attachments, images, audio, or video are visible before
  anyone starts a provider export.
- Added safe first-pass command shapes for `text_only` and `targeted_pages`
  planning before bulk media handling.
- Extended Notion guidance with a large-workspace fallback: split oversized or
  failing workspace exports into smaller top-level page or database batches
  before retrying media-heavy export work.
- Kept the workflow read-only: no provider export, provider API call, OAuth,
  file read, media-byte read, attachment download, archive write, provider URL,
  local path, filename, account id, email, token, or secret value is produced.

## v0.3.75 - 2026-06-16

- Added `wom-kit/docs/ai-response-concept-guide.md`, a beginner-facing guide
  for AI runtimes explaining sha256 object identity vs location, object
  manifests vs zets, and the `objet -> derived text -> zet` layer split.
- Linked the guide from the English and Korean public documentation maps.
- Updated the capability matrix and README status to mark the guide as
  documented-only, with no new command, MCP tool, provider call, upload, source
  read, derived-text capture, draft, mint, transport, or write behavior.

## v0.3.74 - 2026-06-16

- Extended Cloudflare R2 setup guidance with English/Korean dashboard label
  hints and location-based navigation for bucket creation and R2 API token
  creation.
- Clarified that R2 API token creation is reached from the R2 account/overview
  area, not from one bucket's settings page.
- Clarified the post-creation credential split: S3-compatible object access
  uses the Access Key ID plus Secret Access Key pair; the separate Token value
  should not be pasted into chat or stored in WOM unless a future non-S3
  API-token flow explicitly asks for it.
- Configured the MCP stdio entrypoint to use UTF-8 so localized guidance labels
  remain readable on Windows pipes.
- Kept the workflow read-only: no Cloudflare dashboard is opened, no provider
  API is called, no bucket or API token is created, no upload/download occurs,
  and no provider URLs, local paths, tokens, or secret values are echoed.

## v0.3.73 - 2026-06-16

- Extended `archive prehashed-objet-ledger` with `--mime-field <json-field>`
  so externally verified ledgers can carry safe MIME values into
  `objects/manifests/files.jsonl` without echoing row values or reading blob
  bytes.
- Updated `derive-text coverage` so existing derived-text records count as a
  conservative textual signal when older external manifest rows lack useful
  extension/MIME metadata, preventing misleading `0/0` coverage reads after a
  real extraction pass has already been linked.
- Added `wom-kit/schemas/derived-text-capture-manifest-item.schema.json` and
  documented the required `derive-text capture --from-manifest` fields,
  including `tool_version`.
- Kept the workflow closed: no source bytes are read, no providers are called,
  no uploads or downloads are performed, and public/debug output still avoids
  row values, source filenames, local paths, provider URLs, tokens, and secret
  values.

## v0.3.72 - 2026-06-16

- Added `archive imap-mailbox-material-capture-approval-audit <archive-root>
  --material-selection-receipt <archive-relative-json> --approval-receipt
  <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture
  --expected-decision needs_review|approve_once|deny --dry-run --format json`.
- Added aliases `archive imap-material-capture-approval-audit` and
  `archive mailbox-material-capture-approval-audit`.
- The new read-only audit validates that one material capture approval receipt
  matches the selected material receipt, expected capture action, expected
  decision, future-adapter action flags, redaction flags, and closed-action
  flags.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no approval receipt
  path, material-selection receipt path, execution receipt path, candidate
  refs, local paths, tokens, or secret values.

## v0.3.71 - 2026-06-16

- Added `archive imap-mailbox-material-capture-approval-plan <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --decision
  needs_review|approve_once|deny --dry-run|--approve --format json`.
- Added aliases `archive imap-material-capture-approval-plan`,
  `archive mailbox-material-capture-approval-plan`, and
  `archive imap-mailbox-material-capture-approval`.
- The new approval-gated write reuses the material capture execution contract
  and writes one non-secret human decision receipt under
  `receipts/imap/material-capture-approvals/`.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no message material, and echoes no
  material-selection receipt path, execution receipt path, candidate refs,
  local paths, tokens, or secret values.

## v0.3.70 - 2026-06-16

- Added `archive imap-mailbox-material-capture-execution-contract <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --dry-run
  --format json`.
- Added aliases `archive imap-material-capture-execution-contract` and
  `archive mailbox-material-capture-execution-contract`.
- The new read-only gate reuses the material capture request validation and
  returns a future local-adapter execution contract: required inputs, allowed
  actions after separate approval, and a non-secret output receipt shape.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no material-selection
  receipt path, execution receipt path, candidate refs, local paths, tokens, or
  secret values.

## v0.3.69 - 2026-06-16

- Added `archive imap-mailbox-material-capture-request-plan <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --dry-run
  --format json`.
- Added aliases `archive imap-material-capture-request-plan` and
  `archive mailbox-material-capture-request-plan`.
- The new read-only gate validates a non-secret material selection receipt and
  checks whether the selected future material lane authorizes the requested
  body, attachment, or derived-text capture action.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no material-selection
  receipt path, execution receipt path, candidate refs, local paths, tokens, or
  secret values.

## v0.3.68 - 2026-06-16

- Added `archive imap-mailbox-material-selection-record <archive-root>
  --execution-receipt <archive-relative-json> --selection-mode
  human_review_queue|body_candidates|attachment_candidates|derived_text_candidates
  --selected-index <n> --dry-run|--approve --format json`.
- Added aliases `archive imap-material-selection-record` and
  `archive mailbox-material-selection-record`.
- The new approval-gated write records one-based candidate indexes from a
  validated IMAP header metadata scan receipt, creating a non-secret material
  selection receipt under `receipts/imap/material-selections/`.
- Kept message material closed: the command writes no candidate refs, echoes no
  execution receipt path, opens no IMAP connection, reads no environment
  variables, opens no keyring/password manager, reads no message headers,
  bodies, or attachments, creates no derived text, starts no OAuth, and calls no
  providers.

## v0.3.67 - 2026-06-16

- Added `archive imap-mailbox-material-selection-plan <archive-root>
  --execution-receipt <archive-relative-json> --selection-mode
  human_review_queue|body_candidates|attachment_candidates|derived_text_candidates
  --dry-run --format json`.
- Added aliases `archive imap-material-selection-plan` and
  `archive mailbox-material-selection-plan`.
- The new read-only planner consumes an existing non-secret IMAP header
  metadata scan execution receipt and plans the next human material review
  lane before any future body, attachment, or derived-text capture work.
- Kept the gate closed: it opens no IMAP connection, reads no environment
  variables, opens no keyring/password manager, reads no message headers,
  bodies, or attachments, writes no queue files, and echoes no execution receipt
  path, candidate refs, subjects, senders, recipients, local paths, tokens, or
  secret values.

## v0.3.66 - 2026-06-16

- Added `archive external-export-plan <archive-root> --source
  notion|google_drive|generic_workspace --dry-run --format json`.
- The new read-only planner helps users and AI helpers stop before broad
  provider exports that might pull large uploaded files, attachments, images,
  audio, or video into a first local download.
- The planner classifies media risk, recommends text-first, targeted, or
  stop-and-split-media export modes, and links the later `scan-source`,
  `import-external`, and object-storage recommendation commands.
- Kept the export planner closed: it starts no provider export, calls no
  providers, starts no OAuth, reads no files or media bytes, downloads no
  attachments, writes no archive files, and echoes no provider URLs, local
  paths, filenames, account ids, emails, tokens, or secret values.

## v0.3.65 - 2026-06-16

- Extended `archive version <root> --format json` and runtime-context
  `wom_kit_version` pin discovery so an inspected archive root can also find a
  project-local installed-version pin in the parent project root.
- Added redacted logical pin-location reporting through `project_pin.path`,
  `project_pin.pin_root`, and `project_pin.checked_locations`, including
  locations such as `parent_of_archive/.zettel-kasten/installed-version.txt`.
- Normalized UTF-8 BOM-prefixed installed-version files so Windows-created pin
  files do not produce confusing version strings.
- Kept the version check read-only and private by default: it writes no files,
  calls no providers, reads no secrets, and does not echo local absolute paths
  unless the trusted debugging flag is used.

## v0.3.64 - 2026-06-16

- Added `archive beginner-setup-manual <archive-root> --topic
  object_storage_setup_manual --dry-run --format json`.
- Extended `archive object-storage-recommendation` so the recommendation output
  surfaces the proposed bucket name, the bucket naming rule, the exact
  `beginner-setup-manual --topic object_storage_setup_manual` command, and the
  exact `archive object-storage --dry-run` command.
- Added Cloudflare R2 bucket/API-token setup guidance for beginner fields:
  Location, Jurisdiction, Standard storage default, private/public-access
  boundary, Object Read & Write permission, single-bucket scope, TTL/IP
  restriction tradeoffs, and credential-ref bridging.
- Kept the flow read-only: no provider APIs are called, no live pricing or
  bucket availability is checked, no bucket/API token is created, no object
  bytes are read, no files are uploaded, no secrets are read, and no provider
  URLs or secret values are echoed by CLI JSON.

## v0.3.63 - 2026-06-16

- Added `archive imap-mailbox-header-scan-receipt-audit <archive-root>
  --execution-receipt <archive-relative-json> --dry-run|--approve --format json`.
- Added aliases `archive imap-header-scan-receipt-audit` and
  `archive mailbox-header-scan-audit`.
- The new command validates an existing non-secret IMAP header metadata scan
  execution receipt, checks opaque candidate refs and redaction flags, and can
  write a separate non-secret audit receipt under
  `receipts/imap/adapter-execution-audits/`.
- Kept the audit offline and closed: it opens no IMAP connection, reads no
  environment variables, opens no keyring/password manager, reads no
  headers/bodies/attachments, calls no providers, and does not echo the
  execution receipt path or candidate refs.

## v0.3.62 - 2026-06-16

- Added `archive imap-mailbox-header-metadata-scan <archive-root>
  --dry-run|--approve --format json`.
- Added aliases `archive imap-header-metadata-scan` and
  `archive mailbox-header-metadata-scan`.
- Opened the first narrow, approval-gated live IMAP path: app-password auth via
  `env:` refs, IMAP TLS connection, login, read-only inbox select, UID search,
  limited header fetch, opaque candidate refs, and non-secret execution receipt
  writing.
- Kept broad mail ingestion closed: the command returns no username/password
  values, environment variable names, exact credential refs, exact mailbox refs,
  IMAP host values, raw UIDs, Message-ID values, subjects, senders/recipients,
  raw headers, bodies, attachments, provider URLs, or local absolute paths.

## v0.3.61 - 2026-06-16

- Added `archive imap-mailbox-adapter-execution-contract <archive-root>
  --dry-run --format json`.
- Added aliases `archive imap-mailbox-adapter-execution-plan` and
  `archive mailbox-adapter-execution-contract`.
- The new read-only contract wraps IMAP adapter preflight and becomes ready only
  when the adapter manifest, approval receipt, selection plan, and audit
  preview are ready.
- Kept live IMAP execution closed: the command opens no connection, logs into
  nothing, selects no mailbox, reads no headers/bodies/attachments, retrieves
  no credential values, calls no providers, writes no receipts, and writes no
  files.

## v0.3.60 - 2026-06-16

- Added `archive credential-semantic-extraction-recipe <archive-root>
  --source-label <safe-label> --dry-run --format json`.
- Added aliases `archive credential-extraction-recipe` and
  `archive secret-semantic-extraction-recipe`.
- The new read-only recipe helps a human and AI split complex credential notes
  into separate semantic candidates before plaintext migration planning,
  including multi-account, multi-secret, mail, API/CLI token, SSO/passkey,
  recovery-code, wallet/private-key, and status/toggle notes.
- Kept the recipe closed by default: it reads no plaintext files, detects no
  secret values, opens no vaults/keyrings/browser stores, calls no providers,
  writes no files, and returns no secret values to AI.

## v0.3.59 - 2026-06-16

- Added a derived-text completeness signal to
  `archive derive-text coverage <archive-root> --dry-run --format json` and
  alias `archive derive-text-coverage`.
- The new `completeness_signal` block distinguishes manifest-scoped derived
  text coverage from full external workspace/mailbox/cloud-drive mirror
  completion.
- Added `wom-kit/docs/derived-text-completeness-signal.md`, release notes,
  capability matrix coverage, README/documentation map links, and CLI tests.
- Kept the signal read-only and non-secret: it reads no source file bodies,
  scans no external workspaces, calls no providers, reads no secrets, writes no
  files, and echoes no local absolute paths.

## v0.3.58 - 2026-06-16

- Added runtime canonical entrypoint metadata to
  `archive runtime-context <archive-root> --format json`.
- The new `canonical_entrypoints` block names `archive.yml` as the start-here
  file and lists the archive-relative files/directories an AI should treat as
  authoritative for identity, local agent instructions, source bindings,
  provider setup metadata, canonical zets, draft inbox, objets, derived text,
  saved views, and schema context.
- Added `wom-kit/docs/runtime-canonical-entrypoints.md`, release notes,
  capability matrix coverage, README/documentation map links, and CLI tests.
- Kept the check read-only and non-secret: it reads no file bodies, writes no
  files, calls no providers, reads no secrets, and echoes no local absolute
  paths by default.

## v0.3.57 - 2026-06-16

- Added a read-only WOM-kit version truth-source checkpoint:
  `archive --version`, `archive version [inspection-root] --format text|json`,
  and `runtime-context` JSON field `wom_kit_version`.
- The version report names `wom_kit.__version__` as the package source of truth,
  compares it with `wom-kit/pyproject.toml` when running from a source checkout,
  and can compare an optional project pin such as
  `.zettel-kasten/source/installed-version.txt`.
- Added `wom-kit/docs/version-truth-source.md`, release notes, capability
  matrix coverage, README/documentation map links, and CLI tests.
- Kept the check local and non-secret: it writes no files, calls no providers,
  reads no secrets, and redacts local paths by default.

## v0.3.56 - 2026-06-16

- Added approval-gated local IMAP adapter audit receipt writing:
  `archive imap-mailbox-adapter-audit-write --dry-run|--approve` and alias
  `archive mailbox-adapter-audit-write`.
- The command wraps the existing IMAP adapter audit preview and writes exactly
  one non-secret JSON receipt under `receipts/imap/adapter-audits/` only after
  explicit `--approve --reviewed-by <actor>`.
- Added replay protection when the same audit receipt already exists.
- Added `wom-kit/docs/imap-mailbox-adapter-audit-write.md`, public
  documentation links, capability matrix coverage, and CLI tests.
- Kept the command local and non-secret: it exposes no MCP write tool, opens no
  IMAP connection, attempts no login, selects no mailbox, searches no mailbox,
  lists no candidate messages, reads no IMAP UIDs, Message-ID values, headers,
  bodies, or attachments, creates no derived text, retrieves no secrets, starts
  no OAuth, calls no providers, and echoes no email addresses, username values,
  exact account refs, exact credential refs, exact mailbox refs, IMAP host
  values, provider URLs, message ids, subjects, sender or recipient values,
  attachment names, approval receipt paths, selection receipt paths, local
  absolute paths, tokens, or secret values.

## v0.3.55 - 2026-06-16

- Added read-only IMAP adapter preflight planning:
  `archive imap-mailbox-adapter-preflight-plan --dry-run`, alias
  `archive imap-mailbox-adapter-execution-preflight --dry-run`, and alias
  `archive mailbox-adapter-preflight --dry-run`.
- Added MCP tool `imap_mailbox_adapter_preflight_plan` for the same read-only
  preflight surface.
- The preflight composes adapter readiness, manifest status, approval receipt
  verification, mailbox selection planning, and adapter audit receipt preview
  into one final gate before any future live IMAP adapter.
- `preflight_state` returns `ready_for_future_adapter_after_approval` only when
  the adapter manifest is `present_and_schema_valid`, the request package has a
  verified approval receipt, selection is ready, and the audit preview is ready.
- Added `wom-kit/docs/imap-mailbox-adapter-preflight-plan.md`, public
  documentation links, capability matrix coverage, and CLI/MCP tests.
- Kept the preflight read-only: it writes nothing, exposes no live IMAP tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, schema validation issue values, local absolute paths, tokens, or secret
  values.

## v0.3.54 - 2026-06-16

- Extended `archive imap-mailbox-adapter-readiness-plan --dry-run` and MCP
  `imap_mailbox_adapter_readiness_plan` with optional `--adapter-id` /
  `adapter_id` manifest status checks.
- The readiness output now includes `adapter_manifest_summary.status` with
  `not_checked`, `missing`, `present_and_schema_valid`, `invalid`, or
  `blocked`.
- When a safe adapter id is supplied, readiness reads only the archive-relative
  non-secret manifest under `config/imap-adapters/`, validates it against
  `imap-mailbox-adapter-manifest.schema.json`, and checks the archive id,
  adapter id, privacy contract, and closed actions without echoing user-edited
  schema issue values.
- Updated `wom-kit/docs/imap-mailbox-adapter-readiness-plan.md`, the capability
  matrix, README version baseline, release notes, CLI tests, and MCP tests.
- Kept the check read-only: it writes nothing, exposes no live write MCP tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, schema validation issue values, local absolute paths, tokens, or secret
  values.

## v0.3.53 - 2026-06-16

- Added CLI `archive imap-mailbox-adapter-manifest-write --dry-run|--approve`
  with alias `archive mailbox-adapter-manifest-write`.
- `--dry-run` previews the schema-validated non-secret IMAP adapter manifest and
  the write receipt paths without writing files.
- `--approve --reviewed-by <actor>` writes exactly one manifest under
  `config/imap-adapters/` and one non-secret receipt under
  `receipts/imap/adapter-manifests/`, refusing overwrite/replay.
- Added `wom-kit/docs/imap-mailbox-adapter-manifest-write.md`, public
  documentation links, capability matrix coverage, and CLI tests.
- Kept the command local and non-secret: it exposes no MCP live write tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, local absolute paths, tokens, or secret values.

## v0.3.52 - 2026-06-16

- Added JSON Schema `wom-kit/schemas/imap-mailbox-adapter-manifest.schema.json`
  for future IMAP mailbox adapter manifests.
- Updated `archive imap-mailbox-adapter-manifest-plan --dry-run` and MCP
  `imap_mailbox_adapter_manifest_plan` to validate the non-secret manifest
  preview against that schema.
- The preview now returns `schema_validation` metadata so CLI and MCP callers
  can see whether the generated manifest shape passed the contract.
- Updated IMAP manifest documentation, capability matrix coverage, public
  documentation links, and tests for the schema baseline.
- Kept the release read-only: it writes no adapter manifests, executes no live
  adapters, opens no IMAP connection, attempts no login, selects no mailbox,
  searches no mailbox, lists no candidate messages, reads no IMAP UIDs,
  Message-ID values, headers, bodies, or attachments, creates no derived text,
  retrieves no secrets, starts no OAuth, calls no providers, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, selection
  receipt paths, local absolute paths, tokens, or secret values.

## v0.3.51 - 2026-06-16

- Added read-only IMAP adapter manifest previews:
  `archive imap-mailbox-adapter-manifest-plan --dry-run`, alias
  `archive imap-mailbox-adapter-manifest --dry-run`, and alias
  `archive mailbox-adapter-manifest-plan --dry-run`.
- Added MCP tool `imap_mailbox_adapter_manifest_plan` for the same read-only
  preview surface.
- The planner previews a non-secret declaration under `config/imap-adapters/`
  with supported provider labels, operation labels, selection rules, approval
  requirements, audit requirements, privacy contract, and closed actions.
- Added `wom-kit/docs/imap-mailbox-adapter-manifest-plan.md` and public
  documentation links.
- Kept the preview read-only: it writes no adapter manifests, executes no live
  adapters, opens no IMAP connection, attempts no login, selects no mailbox,
  searches no mailbox, lists no candidate messages, reads no IMAP UIDs,
  Message-ID values, headers, bodies, or attachments, creates no derived text,
  retrieves no secrets, starts no OAuth, calls no providers, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, selection
  receipt paths, local absolute paths, tokens, or secret values.

## v0.3.50 - 2026-06-16

- Added read-only IMAP adapter audit receipt previews:
  `archive imap-mailbox-adapter-audit-plan --dry-run`, alias
  `archive imap-mailbox-adapter-audit --dry-run`, and alias
  `archive mailbox-adapter-audit-plan --dry-run`.
- Added MCP tool `imap_mailbox_adapter_audit_plan` for the same read-only
  preview surface.
- The planner composes `imap-mailbox-selection-plan` with safe future adapter
  result metadata, then previews a non-secret receipt shape under
  `receipts/imap/adapter-audits/`.
- Added `wom-kit/docs/imap-mailbox-adapter-audit-plan.md` and public
  documentation links.
- Kept the preview read-only: it writes no audit receipts, selection receipts,
  approval receipts, or adapter manifests, executes no live adapters, opens no
  IMAP connection, attempts no login, selects no mailbox, searches no mailbox,
  lists no candidate messages, reads no IMAP UIDs, Message-ID values, headers,
  bodies, or attachments, creates no derived text, retrieves no secrets, starts
  no OAuth, calls no providers, and echoes no email addresses, username values,
  exact account refs, exact credential refs, exact mailbox refs, IMAP host
  values, provider URLs, message ids, subjects, sender or recipient values,
  attachment names, approval receipt paths, selection receipt paths, local
  absolute paths, tokens, or secret values.

## v0.3.49 - 2026-06-16

- Added read-only IMAP mailbox selection planning:
  `archive imap-mailbox-selection-plan --dry-run`, alias
  `archive imap-mailbox-message-selection-plan --dry-run`, and alias
  `archive mailbox-selection-plan --dry-run`.
- Added MCP tool `imap_mailbox_selection_plan` for the same read-only planning
  surface.
- The planner composes the IMAP operation request package with a safe future
  selector rule such as `newest_first`, `unread_first`, `since_days_window`, or
  `human_review_queue`.
- `selection_state` distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating a selector plan as mailbox access.
- Added `wom-kit/docs/imap-mailbox-selection-plan.md` and public documentation
  links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, searches no mailbox, lists no candidate messages, reads no
  IMAP UIDs, Message-ID values, headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, local absolute
  paths, tokens, or secret values.

## v0.3.48 - 2026-06-15

- Added KeePassXC CSV bulk migration guidance to
  `archive beginner-setup-manual --topic credential_bulk_migration --dry-run`.
- The new beginner topic covers normal import vs passkey import, temporary
  import database creation, UTF-8 CSV settings, header/field separator/text
  qualifier/comment character choices, Group/Title/Username/Password/URL/Notes
  column mapping, `Database > Merge from Database`, expected root/group tree
  shape, slash-created nested groups, and safe cleanup order.
- Linked the bulk migration guide back to
  `credential-plaintext-migration-plan` so the plan-level and screen-level
  workflows are easier to follow together.
- Updated the beginner setup manual, capability matrix, README summary, and
  release notes.
- Kept the topic read-only: it reads no CSV, opens no KeePassXC window, creates
  no temporary database, imports or merges no vault, records no database path,
  deletes no temporary files, writes nothing, and echoes no secret values,
  usernames, emails, provider URLs, local paths, CSV paths, or vault paths.

## v0.3.47 - 2026-06-15

- Added read-only IMAP mailbox adapter readiness checks:
  `archive imap-mailbox-adapter-readiness-plan --dry-run`, alias
  `archive imap-mailbox-adapter-plan --dry-run`, and alias
  `archive mailbox-adapter-readiness --dry-run`.
- Added MCP tool `imap_mailbox_adapter_readiness_plan` for the same
  read-only readiness surface.
- The readiness planner composes the IMAP operation request package with local
  runtime module checks for the future adapter path.
- `readiness_state` now distinguishes `ready_for_request_package`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating runtime readiness as live mailbox access.
- Added `wom-kit/docs/imap-mailbox-adapter-readiness-plan.md` and public
  documentation links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, reads no headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message headers, message
  bodies, attachment names, approval receipt paths, local absolute paths,
  tokens, or secret values.

## v0.3.46 - 2026-06-15

- Added read-only IMAP mailbox operation request packages:
  `archive imap-mailbox-operation-request-plan --dry-run`, alias
  `archive imap-mailbox-request-plan --dry-run`, and alias
  `archive mailbox-operation-request-plan --dry-run`.
- Added MCP tool `imap_mailbox_operation_request_plan` for the same
  read-only request package surface.
- The package composes `imap-mailbox-plan` and `credential-policy-check` for
  `mail_source_read` into one future-adapter approval gate.
- `request_state` distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating missing human approval as live execution readiness.
- `approve_once` requires a verified archive-relative approval receipt before
  the request package can become `ready_for_future_adapter_after_approval`.
- Added `wom-kit/docs/imap-mailbox-operation-request-plan.md` and public
  documentation links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, reads no headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message headers, message
  bodies, attachment names, approval receipt paths, local absolute paths,
  tokens, or secret values.

## v0.3.45 - 2026-06-15

- Added read-only object-storage operation request packages:
  `archive object-storage-operation-request-plan --dry-run`, alias
  `archive object-storage-request-plan --dry-run`, and alias
  `archive objet-storage-operation-request --dry-run`.
- Added MCP tool `object_storage_operation_request_plan` for the same
  read-only request package surface.
- The package composes provider readiness, object target validation,
  presigned URL planning or objet-ref resolution, and `credential-policy-check`
  for `object_storage_request` into one future-adapter approval gate.
- `request_state` now distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating missing human approval as live execution readiness.
- `approve_once` requires a verified archive-relative approval receipt before
  the request package can become `ready_for_future_adapter_after_approval`.
- Added `wom-kit/docs/object-storage-operation-request-plan.md` and public
  documentation links.
- Kept the planner read-only: it calls no providers, retrieves no secrets,
  creates no presigned URLs, uploads or downloads nothing, lists no remote
  metadata, reads no object bytes, checks no remote availability, writes no
  files or receipts, and echoes no bucket names, prefixes, provider URLs,
  generated URLs, local absolute paths, exact credential refs, approval receipt
  paths, provider setup receipt paths, tokens, or secret values.

## v0.3.44 - 2026-06-15

- Added a KeePassXC 2.7.x first-vault walkthrough to
  `archive beginner-setup-manual --store-id keepassxc --platform windows
  --dry-run`.
- The walkthrough now gives screen-by-screen and field-by-field guidance for
  the new database wizard: general screen, encryption settings, credentials,
  save dialog, and first entry.
- Added WOM-context field decisions for first local KeePassXC vaults:
  KDBX 4.0, AES-256, Argon2d, and leaving KeePassXC automatic/recommended KDF
  tuning values alone.
- Added explicit conflict guidance for Argon2d vs Argon2id: WOM's beginner
  recommendation is scoped to a local offline KDBX vault threat model; stricter
  workplace/school/regulatory policy still wins when present.
- Kept the manual read-only: it does not open KeePassXC, create a database,
  store database paths, read or write secrets, read environment variables, call
  providers, install tools, or write files.

## v0.3.43 - 2026-06-15

- Added manifest-aware object storage recommendations.
- `archive object-storage-recommendation --scenario auto_from_manifest
  --dry-run` now reads aggregate metadata from `objects/manifests/files.jsonl`
  to infer a scenario before provider setup planning.
- Recommendation output now includes `manifest_analysis`, `scenario_source`,
  and `rough_cost_estimates` with total manifest size, dominant content class,
  content-class percentages, and non-live storage/egress estimate fields.
- Rough estimates use a static 2026-06-15 public-pricing snapshot for
  comparison only; live pricing APIs are not called and humans must still check
  official calculators/docs before spending money.
- Kept the command read-only: it writes no files, reads no object bytes, calls
  no providers, checks no bucket availability, creates no buckets, uploads or
  downloads nothing, creates no presigned URLs, and echoes no object filenames,
  local paths, provider account URLs, tokens, or secret values.

## v0.3.42 - 2026-06-15

- Updated `archive connected-accounts --dry-run` so account-map success is
  separate from the optional local credential catalog status.
- Malformed ignored local credential catalog rows now appear under nested
  `credential_catalog.ok`, `credential_catalog.status`, and
  `credential_catalog.blockers` instead of making the whole connected account
  overview return `ok: false`.
- Kept true account-map blockers, such as unsafe account labels or unreadable
  provider/source binding files, as top-level blockers.
- Updated connected-accounts documentation and capability matrix language for
  the split status model.
- Kept the command read-only: it still writes no files, opens no password
  manager/keyring/browser store, reads no environment variables, calls no
  providers, opens no IMAP connection, reads no source bytes, and echoes no
  exact credential refs, emails, usernames, tokens, provider URLs, local paths,
  or secret values.

## v0.3.41 - 2026-06-15

- Added read-only object storage adapter readiness commands:
  `archive object-storage-adapter-readiness-plan --dry-run`, alias
  `archive object-storage-adapter-plan --dry-run`, and alias
  `archive objet-storage-adapter-readiness --dry-run`.
- Added MCP tool `object_storage_adapter_readiness_plan` for the same
  read-only readiness surface.
- The planner bridges `provider-status`, object-storage setup receipts,
  credential access broker requirements, credential policy checks, human
  approval receipts, adapter manifests, and future audit receipts without
  executing an adapter.
- Added `wom-kit/docs/object-storage-adapter-readiness-plan.md` and public
  documentation links.
- Kept the command read-only: it calls no providers, retrieves no secrets,
  creates no presigned URLs, uploads or downloads nothing, reads no object
  bytes, checks no remote availability, writes no files or receipts, and echoes
  no bucket names, prefixes, provider URLs, local absolute paths, exact
  credential refs, provider setup receipt paths, tokens, or secret values.

## v0.3.40 - 2026-06-15

- Added read-only presigned URL planning commands:
  `archive presigned-url-plan --dry-run`, alias
  `archive object-presigned-url-plan --dry-run`, and alias
  `archive objet-presigned-url-plan --dry-run`.
- Added MCP tool `presigned_url_plan` for the same read-only planning surface.
- The planner reuses `resolve-objet-ref`, validates `object_id`, safe
  `store_ref`, operation, TTL, and object-storage binding presence before any
  future provider adapter.
- Added `wom-kit/docs/presigned-url-plan.md` and public documentation links.
- Kept the command read-only: it creates no presigned URLs, calls no providers,
  retrieves no credential values, reads no object bytes, uploads or downloads
  nothing, writes no files or receipts, and echoes no provider URLs, local
  absolute paths, exact credential refs, bucket URLs, tokens, or secret values.

## v0.3.39 - 2026-06-15

- Added read-only object storage recommendation commands:
  `archive object-storage-recommendation --dry-run`, alias
  `archive object-storage-match --dry-run`, and alias
  `archive objet-storage-recommendation --dry-run`.
- The matcher maps human scenarios such as `personal_low_ops`,
  `backup_cost_sensitive`, `aws_native`, and `google_cloud_native` to existing
  WOM-kit object-storage setup provider ids and returns the next
  `archive object-storage --dry-run` command shape.
- Added `wom-kit/docs/object-storage-recommendations.md` and public
  documentation links.
- Kept the command read-only: it calls no providers, performs no live price
  lookup, checks no bucket availability, creates no buckets, uploads or
  downloads no files, reads no object bytes, creates no presigned URLs, starts
  no OAuth, reads no secret values, writes no files, and echoes no provider
  URLs, local paths, object filenames, tokens, or secret values.

## v0.3.38 - 2026-06-15

- Added read-only connected account overview commands:
  `archive connected-accounts --dry-run`, alias `archive accounts --dry-run`,
  and alias `archive account-status --dry-run`.
- The overview bridges provider bindings, IMAP mailbox source accounts, and the
  ignored local credential-ref inventory into one account/status map.
- Added `wom-kit/docs/connected-accounts.md` and public documentation links.
- Kept the command read-only: it reads metadata only, writes no files, opens no
  vault/keyring/browser store, reads no environment variables or source bytes,
  starts no OAuth, calls no providers, opens no IMAP connection, reads no mail,
  and echoes no exact credential refs, local paths, usernames, emails, tokens,
  provider URLs, or secret values.

## v0.3.37 - 2026-06-15

- Added read-only beginner setup manual commands:
  `archive beginner-setup-manual --dry-run`, alias
  `archive first-use-setup-manual --dry-run`, and alias
  `archive setup-manual --dry-run`.
- The manual bridges existing credential and derived-text setup surfaces by
  explaining first vault setup, safe non-secret labels, KeePassXC-style naming,
  derived-text tool readiness, private `--tool-hints` files, and the next
  dry-run commands to execute.
- Added `wom-kit/docs/beginner-setup-manual.md` and public documentation links.
- Kept the manual read-only: it opens no vault, reads no keyring or environment,
  installs no tools, executes no tools, reads no source bytes, writes no files,
  runs no OCR/parsers/ASR/provider calls, and echoes no local paths, tool hint
  paths, usernames, emails, tokens, provider URLs, or secret values.

## v0.3.36 - 2026-06-15

- Added `--tool-hints <json>` to read-only derived-text doctor commands:
  `archive derive-text doctor --tool-hints <json> --dry-run` and
  `archive derive-text-doctor --tool-hints <json> --dry-run`.
- Tool hints let a local user provide executable path hints for PATH-missing
  extractors such as `soffice`, `libreoffice`, `tesseract`, and `hwp5txt`
  without echoing those paths in JSON or text output.
- Fixed the doctor readiness summary so a tool with multiple executable probes,
  such as LibreOffice via `soffice` or `libreoffice`, is not listed as missing
  when any accepted probe is available.
- Kept the doctor read-only: it only checks local path existence for user-supplied
  hints, installs nothing, executes nothing, reads no source bytes, writes
  nothing, and emits no tool paths, import paths, local absolute paths, provider
  URLs, source bodies, usernames, or secret values.

## v0.3.35 - 2026-06-15

- Added read-only derived-text toolchain doctor commands:
  `archive derive-text doctor --dry-run` and
  `archive derive-text-doctor --dry-run`.
- The doctor checks boolean readiness for Python module probes (`docx`,
  `openpyxl`, `pptx`, `fitz`) and executable probes (`soffice`,
  `libreoffice`, `tesseract`, `hwp5txt`) without echoing executable paths,
  import paths, local absolute paths, source filenames, provider URLs, source
  bodies, usernames, or secret values.
- Added family readiness output for plain text/markup, OOXML Word,
  spreadsheets, presentations, legacy Office, HWP/HWPX, PDF, image scan, and
  audio routes.
- Kept the doctor read-only: it installs nothing, reads no source bytes, runs
  no OCR/parsers/ASR/vision calls, calls no providers, writes no derived text,
  writes no receipts, drafts no zets, and mints nothing.

## v0.3.34 - 2026-06-15

- Added read-only derived-text coverage gate commands:
  `archive derive-text coverage --dry-run` and
  `archive derive-text-coverage --dry-run`.
- Added read-only derived-text toolchain recommendation commands:
  `archive derive-text toolchain --extension <ext> --dry-run` and
  `archive derive-text-toolchain --extension <ext> --dry-run`.
- Added read-only derived-text agent operating contract commands:
  `archive derive-text agent-contract --dry-run` and
  `archive derive-text-agent-contract --dry-run`.
- The coverage gate compares `objects/manifests/files.jsonl` with
  `objects/manifests/derived-text.jsonl`, classifies textual candidates by
  extension/MIME, flags `missing_derived_text` and
  `needs_password_or_encrypted`, and blocks completion claims while uncovered
  textual objets remain.
- The toolchain recommendation surface covers PDF, Office OOXML, legacy Office,
  HWP/HWPX, image, audio, and plain-text/markup families without running OCR,
  parsers, ASR, LLM vision, or provider APIs.
- Kept the release read-only and privacy-preserving: it reads no source bytes,
  echoes no source filenames, local absolute paths, provider URLs, or source
  bodies, writes no derived text or receipts, drafts no zets, and mints
  nothing.

## v0.3.33 - 2026-06-15

- Added CLI-only `archive credential-keepassxc-write --approve` for the first
  minimal live KeePassXC credential write adapter.
- Reused approval receipt verification and `credential_policy_check` before
  execution, and required one scoped `approve_once` receipt for each write.
- Invoked only `keepassxc-cli add --password-prompt` in approved local CLI
  mode, so the database unlock secret and new entry password stay in the local
  terminal/KeePassXC CLI prompt instead of argv, stdin, chat, JSON output, or
  receipts.
- Added non-secret execution receipts under
  `receipts/credentials/keepassxc-writes/` and blocked replay with the same
  approval receipt once a write execution receipt exists.
- Kept MCP preview-only: no live KeePassXC write tool is exposed through MCP.
- Added `wom-kit/docs/credential-keepassxc-write.md` plus CLI/docs coverage
  for verified receipts, database-path non-echo, secret non-echo, replay
  blocking, and the CLI-only execution boundary.

## v0.3.32 - 2026-06-15

- Added read-only CLI `archive credential-keepassxc-command-plan --dry-run`
  and MCP `credential_keepassxc_command_plan` for previewing a safe
  KeePassXC CLI add-command shape after approval receipt verification.
- Added CLI aliases `archive keepassxc-command-plan --dry-run` and
  `archive credential-keepassxc-write-plan --dry-run`.
- Required `--approval-receipt <path>` and re-used `credential_policy_check`
  so the plan is blocked unless the written approval receipt verifies for the
  same archive, credential, action, store, consumer, and `approve_once`
  decision.
- Kept the release non-executing and non-secret: it runs no `keepassxc-cli`,
  opens no KeePassXC vaults, stores no `.kdbx` paths, reads no database
  passwords, reads no plaintext files, pipes no secrets to stdin, places no
  secret values in argv, writes no vault entries, and keeps
  `live_execution_allowed_now` false.
- Added `wom-kit/docs/credential-keepassxc-command-plan.md` plus CLI/MCP/docs
  coverage for receipt verification, dry-run-only behavior, allowed-root
  enforcement, no-write behavior, and privacy boundaries.

## v0.3.31 - 2026-06-15

- Added local CLI approval receipt writing through
  `archive credential-access-approval --approve --reviewed-by <actor>` for
  recording one non-secret credential access approval receipt under
  `receipts/credentials/access-approvals/`.
- Kept `archive credential-access-approval-plan --dry-run` and MCP
  `credential_access_approval_plan` as preview-only surfaces; MCP still cannot
  write approval receipts.
- Updated `archive credential-policy-check --dry-run` and MCP
  `credential_policy_check` so they can verify an archive-relative approval
  receipt with `--approval-receipt <path>` before any future adapter execution.
- Preserved secret boundaries: the writer records no secret values, no exact
  credential refs, no usernames, no email addresses, no local paths, no provider
  URLs, and it opens no vault, keyring, browser store, environment variable,
  plaintext file, provider API, OAuth flow, or live adapter.
- Added CLI/docs coverage for receipt preview, receipt write, duplicate/no-mode
  blockers, policy receipt verification, no-write MCP behavior, and privacy
  boundaries.

## v0.3.30 - 2026-06-15

- Added read-only CLI `archive credential-policy-check --dry-run` and MCP
  `credential_policy_check` for evaluating a proposed credential use request
  before any future live adapter can run.
- Added CLI aliases `archive credential-access-policy-check --dry-run` and
  `archive secret-policy-check --dry-run`.
- Added policy results `ready_after_approval_receipt`, `needs_human_review`,
  `denied_by_human_decision`, `denied_by_policy`, and `blocked`.
- Added a concrete policy object preview for approval decision, store kind,
  adapter kind, adapter operation, action kind, and non-echo rules.
- Kept the checker non-mutating and non-executing: it writes no approval
  receipts, executes no live adapters, opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs, or
  OAuth flows, and even a passing result keeps `live_execution_allowed_now`
  false.
- Added `wom-kit/docs/credential-policy-check.md` plus CLI/MCP/docs tests for
  policy pass, policy denial, dry-run-only behavior, allowed-root enforcement,
  no-write behavior, and privacy boundaries.

## v0.3.29 - 2026-06-15

- Added read-only CLI `archive credential-plaintext-migration-plan --dry-run`
  and MCP `credential_plaintext_migration_plan` for planning how a
  human-selected plaintext note could later be migrated into a real
  vault/keyring/store without returning secrets to AI.
- Added CLI aliases `archive secret-migration-plan --dry-run` and
  `archive credential-import-plan --dry-run`.
- Required a safe `--source-label` instead of accepting or echoing local file
  paths, and linked target store routing to the v0.3.28 vault onboarding layer.
- Kept the release strictly non-mutating and non-secret: it reads no plaintext
  files, prints no plaintext file paths, hashes no plaintext bytes, detects no
  secret values, returns no candidate secret values to AI, opens no vaults,
  keyrings, browser stores, environment variables, provider APIs, OAuth flows,
  or adapter runners, deletes no plaintext notes, and writes no files.
- Added `wom-kit/docs/credential-plaintext-migration-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, pathless source
  labeling, no-write behavior, and privacy boundaries.

## v0.3.28 - 2026-06-15

- Added read-only CLI `archive credential-vault-onboarding-plan --dry-run`
  and MCP `credential_vault_onboarding_plan` for planning how a human-selected
  external vault, password manager, platform password manager, OS keyring,
  developer secret manager, or environment injection surface should fit WOM.
- Added CLI aliases `archive credential-vault-onboarding --dry-run` and
  `archive secret-vault-onboarding-plan --dry-run`.
- Added safe store-id routing for `recommended`, `keepassxc`, `bitwarden`,
  `1password`, `browser_or_platform_password_manager`, `os_keyring`,
  `developer_secret_manager`, and `environment_variable`.
- Linked the onboarding layer to credential refs, inventory, broker planning,
  approval previews, adapter readiness, adapter manifests, and adapter audit
  previews without opening or reading any real vault/keyring/store.
- Kept the release strictly non-mutating and non-secret: it opens no password
  managers, browser stores, OS keyrings, environment variables, plaintext
  secret files, provider APIs, OAuth flows, or adapter runners; writes no
  files; and includes no secret values, exact credential refs, usernames, email
  addresses, tokens, local paths, provider URLs, passwords, or API keys.
- Added `wom-kit/docs/credential-vault-onboarding-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  planner-chain linkage, and privacy boundaries.

## v0.3.27 - 2026-06-15

- Added read-only CLI `archive credential-adapter-audit-plan --dry-run` and
  MCP `credential_adapter_audit_plan` for previewing a non-secret future
  credential adapter audit receipt.
- Added CLI aliases `archive credential-adapter-audit --dry-run` and
  `archive secret-adapter-audit-plan --dry-run`.
- Defined the future audit boundary after credential refs, adapter manifests,
  readiness checks, human approval receipts, and local adapter operations.
- Kept the audit layer non-mutating and non-executing: it writes no receipts or
  manifests, executes no live adapters, opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs, or
  approval writers, and includes no secret values, exact credential refs,
  usernames, email addresses, tokens, local paths, provider URLs, passwords, or
  API keys.
- Added `wom-kit/docs/credential-adapter-audit-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  non-execution, and privacy boundaries.

## v0.3.26 - 2026-06-15

- Added read-only CLI `archive credential-adapter-manifest-plan --dry-run`
  and MCP `credential_adapter_manifest_plan` for previewing a non-secret
  future credential adapter manifest.
- Added CLI aliases `archive credential-adapter-manifest --dry-run` and
  `archive secret-adapter-manifest-plan --dry-run`.
- Added JSON schema `wom-kit/schemas/credential-adapter-manifest.schema.json`
  and schema validation in the manifest preview output.
- Kept the manifest layer non-mutating and non-secret: it writes no manifests,
  opens no vaults, keyrings, browser stores, environment variables, plaintext
  secret files, provider APIs, approval receipt writers, or audit receipt
  writers, and it includes no secret values, exact credential refs, local
  absolute paths, provider account values, provider URLs, passwords, tokens, or
  API keys.
- Added `wom-kit/docs/credential-adapter-manifest-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, schema validity,
  no-write behavior, and privacy boundaries.

## v0.3.25 - 2026-06-15

- Added read-only CLI `archive credential-adapter-readiness-plan --dry-run`
  and MCP `credential_adapter_readiness_plan` for previewing the contract a
  future local credential adapter must satisfy before using a password manager,
  OS keyring, browser/platform password manager, developer secret manager,
  environment injection surface, or future wallet.
- Added CLI aliases `archive credential-adapter-plan --dry-run` and
  `archive secret-adapter-readiness --dry-run`.
- Added adapter readiness coverage for resolving a credential for one approved
  action, writing a new secret, rotating a secret, plaintext secret migration,
  browser login fill, and metadata-only listing.
- Kept the release strictly non-mutating: it opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs,
  approval receipt writers, or audit receipt writers, and it never echoes exact
  credential refs or secret values.
- Added `wom-kit/docs/credential-adapter-readiness-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.

## v0.3.24 - 2026-06-15

- Added read-only CLI `archive credential-access-approval-plan --dry-run` and
  MCP `credential_access_approval_plan` for previewing a future
  human-reviewed credential access approval receipt.
- Added preview decisions `needs_review`, `approve_once`, and `deny`; even
  `approve_once` remains a non-mutating preview and grants no live access in
  this release.
- Kept exact credential ref values and secret values out of the receipt preview;
  the preview reports only safe metadata such as credential id, kind, provider,
  purpose, ref store, ref prefix, action kind, store kind, and consumer label.
- Added `wom-kit/docs/credential-access-approval-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.
- Fixed the secret scanner so declared credential refs such as
  `secret:keepassxc-personal-mail` and `keyring:openai-api-key` do not trigger
  `secret_value_detected` when recorded in the local credential-ref catalog.
  Raw secret-like values are still detected.

## v0.3.23 - 2026-06-15

- Added read-only CLI `archive credential-access-broker-plan --dry-run` and
  MCP `credential_access_broker_plan` for planning a future local credential
  access broker without retrieving secrets.
- Defined broker action kinds for mail source reads, model API calls, OCR API
  calls, object-storage requests, CLI token auth, browser login fill, and
  plaintext secret migration planning.
- Kept exact credential ref values and raw secret values out of structured
  output; the planner reports only safe metadata such as credential id, kind,
  provider, purpose, ref store, and ref prefix.
- Documented the broker boundary for future AI use: AI requests a credential
  capability by purpose/ref, while a local approved adapter uses the secret for
  the approved action without echoing it into chat, zets, receipts, logs,
  prompts, or public docs.
- Added `wom-kit/docs/credential-access-broker-plan.md` plus CLI/MCP/docs tests
  for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.

## v0.3.22 - 2026-06-14

- Added read-only CLI `archive credential-store-recommendation --dry-run` and
  MCP `credential_store_recommendation` for scenario-based recommendations
  across KeePassXC-style offline vaults, Bitwarden/1Password-style syncing
  managers, browser/platform password managers, OS keyrings, developer secret
  managers, automation env refs, local app adapters, and institutional mail.
- Defined WOM compatibility rules for `secret:`, `keyring:`, `env:`, and
  future `wallet:` refs in the context of human password vault choice.
- Documented the future credential access broker boundary: AI should request a
  credential capability by purpose/ref, while a local approved adapter uses the
  secret without echoing it into chat, zets, receipts, logs, prompts, or public
  docs.
- Added `wom-kit/docs/credential-store-recommendations.md` plus CLI/MCP/docs
  tests for read-only behavior, scenario coverage, allowed-root enforcement,
  no-write behavior, and non-echo guarantees.

## v0.3.21 - 2026-06-14

- Added read-only CLI `archive credential-ref-inventory --dry-run` and MCP
  `credential_ref_inventory` for listing known credential refs without echoing
  exact ref values or secrets.
- Added ignored local catalog guidance for
  `profiles/local/credential-refs.local.yml` so a human can remember credential
  ids, kinds, providers, purposes, and store prefixes while keeping passwords,
  tokens, API keys, and account values outside WOM archive records.
- Improved IMAP mailbox planning feedback when a credential-store ref such as
  `keyring:*` is accidentally passed as `account_ref`; `account_ref` is now
  explained as a non-secret account label, while `keyring:`, `env:`, `secret:`,
  and `wallet:` refs belong in username, app-password, OAuth-token, or generic
  credential fields.
- Added `wom-kit/docs/credential-ref-inventory-and-onboarding.md` plus
  CLI/MCP/docs tests for dry-run-only behavior, allowed-root enforcement,
  no-write behavior, and non-echo guarantees.

## v0.3.20 - 2026-06-14

- Added read-only CLI `archive credential-ref-plan --dry-run` and MCP
  `credential_ref_plan` for planning mail, OpenAI API, OCR API, provider,
  object-storage, and backup credential references without storing secrets.
- Defined safe credential ref prefixes `env:`, `keyring:`, `secret:`, and
  `wallet:` so archive records can point to local secret stores without
  containing the secret value.
- Kept the boundary conservative: the plan writes nothing, reads no environment
  variables, opens no OS keyring, starts no OAuth, calls no providers, calls no
  OpenAI or paid OCR APIs, and blanks invalid raw secret inputs before returning
  structured output.
- Added `wom-kit/docs/credential-store-contract.md` plus CLI/MCP/docs tests for
  dry-run-only behavior, allowed-root enforcement, raw-secret redaction, and
  public documentation coverage.

## v0.3.19 - 2026-06-14

- Added read-only CLI `archive imap-mailbox-plan --dry-run` and MCP
  `imap_mailbox_plan` for provider-neutral IMAP mailbox source planning across
  Gmail, Naver, and generic IMAP hosts.
- Added `imap_mailbox` as a registered source type while keeping live IMAP
  scans fail-closed in this release; `scan-source` now directs operators back
  to the planning step for safe credential refs.
- Kept the mail boundary conservative: the plan writes nothing, connects to no
  server, attempts no login, reads no headers, bodies, or attachments, sends no
  mail, deletes no mail, changes no flags, and accepts credential refs instead
  of raw usernames, emails, passwords, or tokens.
- Added `wom-kit/docs/imap-mailbox-source.md` plus CLI/MCP/source-map tests for
  dry-run-only behavior, registration shape, scan blocking, and private-value
  redaction.
- Tightened zettel path guidance so absolute `--path` inputs point users back to
  archive-relative `inbox/` or `zettels/` paths and `--zettel-id`.

## v0.3.18 - 2026-06-14

- Added read-only CLI `archive zettel-objet-links --path <zet.md>|--zettel-id
  <id> --dry-run` and MCP `zettel_objet_links` for zettel-level objet link
  previews.
- The preview scans one non-redacted zettel for `sha256:<hex>` and
  `objet:sha256:<hex>` refs, then reuses `resolve-objet-ref` to return safe
  local archive-relative candidates and external store labels.
- Kept the preview conservative: it writes nothing, echoes no zettel body text
  or frontmatter values, echoes no absolute local paths or provider URLs, reads
  no object bytes, calls no providers, creates no presigned URLs, and blocks
  redacted zettels.
- Added `wom-kit/docs/zettel-objet-links.md` and tests for CLI/MCP behavior,
  dry-run-only enforcement, and privacy boundaries.

## v0.3.17 - 2026-06-14

- Added read-only CLI `archive resolve-objet-ref --object-id sha256:<hex>
  --dry-run` and MCP `resolve_objet_ref` for the first reading-side objet
  reference resolver.
- The resolver reads `objects/manifests/files.jsonl` and reports safe local
  archive-relative candidates plus external store labels for one manifest
  `object_id`.
- Kept the resolver non-mutating and conservative: it writes nothing, echoes no
  absolute local paths or provider URLs, reads no object bytes, re-hashes no
  object bytes, calls no providers, creates no presigned URLs, downloads
  nothing, uploads nothing, and does not decide deletion safety.
- Added `wom-kit/docs/objet-ref-resolution.md` and documentation tests for the
  resolver boundary.

## v0.3.16 - 2026-06-14

- Added `wom-kit/docs/notion-page-snapshot-model.md` to define Notion
  `recordMap` / `blocks` JSON as provider page snapshot source objets, separate
  from extracted derived text and human-authored zets.
- Clarified `store_ref` semantics for prehashed external objet ledgers:
  `object_id` identifies the bytes, `store_kind` names the storage family, and
  `store_ref` is only a reviewed safe external-store label, not a raw path,
  URL, token, or proof of byte availability.
- Linked the model from the Notion three-store example, source objet storage
  policy, text provenance hierarchy, README, public documentation map, and
  capability matrix without adding Notion API calls, provider sync, extraction
  helpers, page-snapshot schemas, or byte materialization adapters.

## v0.3.15 - 2026-06-14

- Added approval-gated CLI `archive project-intake-unpack-choice
  --dry-run|--approve` and MCP `project_intake_unpack_choice` so a human can
  record one reviewed `item-0001` style unpack choice after the queue step.
- The new choice receipt stores the opaque item ref, intended action, completed
  project-intake receipt link, and public-safe queue digest without exposing
  staged entry names, local paths, file bodies, or choice notes in command
  output.
- Kept source-intake, capture, drafting, minting, provider sync, and cleanup as
  separate gates after the human choice receipt.

## v0.3.14 - 2026-06-14

- Added read-only CLI `archive project-intake-unpack-queue --dry-run` and MCP
  `project_intake_unpack_queue` for the first practical "unpacking boxes"
  layer in the human-guided project intake flow.
- The unpack queue returns opaque `item-0001` style refs plus coarse
  kind/extension/size hints so an AI can ask which staged item the human wants
  to unpack next without exposing entry names, local paths, file bodies, or
  decision values.
- Documented the queue between project-intake receipt review and per-item
  `project-intake-item-plan`, while keeping source-intake, capture, drafting,
  minting, provider sync, and cleanup as separate approval gates.

## v0.3.13 - 2026-06-14

- Strengthened `wom-kit/docs/human-artifact-store-contract.md` as the shared
  contract for user-selected surfaces such as WordPress, Joplin, Notion,
  Obsidian, and generic Markdown/workspace apps.
- Added a role matrix and adapter questions that separate raw data stores,
  human-readable artifacts, projection surfaces, and system/AI records so app
  names do not become implicit WOM architecture.
- Added a capture-action shape for future note/report/handoff workflows:
  explicit human capture first, then a separate local WOM receipt/source-map
  record outside the app.
- Linked the contract from README and the public documentation maps, and pointed
  ZET surface prototypes back to the shared contract before future app-specific
  adapters write anything.

## v0.3.12 - 2026-06-14

- Updated `wom-kit/docs/project-intake-cookbook.md` with a bulk raw-preservation
  to selective promotion bridge for large already-hashed migrations:
  `prehashed-objet-ledger` registers raw object manifests first, while the
  project-intake cookbook remains the human-guided path for selected drafts and
  zets.
- Clarified that `archive-objets/` is the recommended local staging root in the
  cookbook rehearsal, not a requirement to move an existing external
  content-addressed store.
- Added copy/paste-friendly `$sourceIntakeReceipt` and `$selectionJson`
  placeholders for the source-intake-record to capture-selection handoff.

## v0.3.11 - 2026-06-14

- Extended `archive prehashed-objet-ledger` so CLI `--ledger` may be repeated,
  allowing retrieval, deep, and workspace download ledgers to be deduped across
  one dry-run/approval pass.
- Added skipped-row accounting for prehashed ledger rows with null or empty
  `sha256`, so aid-dedup style rows can be ignored without blocking approval;
  malformed non-empty sha values remain invalid.

## v0.3.10 - 2026-06-14

- Added `wom-kit/docs/project-intake-cookbook.md`, a fake-archive rehearsal
  walkthrough for the manual project-intake spine from session planning through
  answer receipt, source-intake, capture selection, capture, draft/mint gates,
  and cleanup verification.
- Strengthened the project-intake-to-objet-capture roundtrip regression so it
  now creates the project-intake receipt through
  `archive project-intake-record-answer` semantics before passing that receipt
  into source-intake and capture context checks.
- Updated README release-baseline bookkeeping to v0.3.10, including the Korean
  README's release tag list.

## v0.3.9 - 2026-06-14

- Added approval-gated CLI `archive project-intake-record-answer --dry-run|--approve`
  to append exactly one human-reviewed project-intake answer to a new or
  existing decisions receipt without echoing current or previous answer values,
  running source intake, capturing objets, drafting, minting, calling providers,
  or cleaning staged folders.

## v0.3.8 - 2026-06-14

- Added read-only CLI `archive project-intake-staging-guide --dry-run` and MCP
  `project_intake_staging_guide` to show the recommended local objet-store
  intake path for one project slug without creating folders, moving files,
  uploading, capturing, drafting, minting, or cleaning.
- Added read-only CLI `archive project-intake-session-guide --dry-run` and MCP
  `project_intake_session_guide` to show the next safe human-guided intake step
  from a project slug, staged folder, or existing decisions receipt without
  echoing decision values, reading file bodies, writing decisions, capturing,
  drafting, minting, uploading, cleaning, or authorizing automatic execution.
- Added read-only CLI `archive project-intake-next-question --dry-run` and MCP
  `project_intake_next_question` so AI-assisted intake can ask one
  human-review question at a time without echoing decision values, writing
  decisions, capturing, drafting, minting, uploading, or cleaning.
- Added read-only CLI `archive project-intake-decision-template --dry-run` and
  MCP `project_intake_decision_template` to produce the next answer's decision
  JSON shape without filling answer values, echoing previous answers, approving
  receipts, or writing files.
- Added read-only CLI `archive project-intake-item-plan --dry-run` and MCP
  `project_intake_item_plan` to preview the next source-intake dry-run route for
  one human-selected file while redacting local paths and avoiding capture,
  drafting, minting, uploads, cleanup, or selection-manifest generation.
- Added approval-gated CLI `archive source-intake-record --dry-run|--approve`
  to validate a reviewed `source-intake --dry-run` JSON file and preserve the
  redacted plan under `receipts/sources/` for later capture evidence without
  reading file bodies, calculating content hashes, or calling providers.
- Added approval-gated CLI `archive objet-capture-selection
  --dry-run|--approve` to build a reviewed `objet-capture --selection`
  manifest from one staged file and one recorded source-intake plan. It hashes
  the selected staged file to bind `approved_object_id`, writes only the
  selection manifest on approve, and does not capture bytes, append object
  manifest records, draft, mint, upload, or clean staged originals.
- Added CLI `archive prehashed-objet-ledger --dry-run|--approve` for
  already-hashed external content-addressed ledgers, including Notion
  source-export ledgers. Dry-run previews registration without echoing row
  values; approved mode appends external manifest records and writes a receipt
  without reading blob bytes, copying objects, uploading, drafting, minting, or
  claiming that `objet-capture` can skip byte verification today. MCP remains a
  read-only `prehashed_objet_ledger_preview`.
- Added read-only CLI `archive zet-surface-prototype --dry-run` and MCP
  `zet_surface_prototype_plan` for user-selected ZET surface prototypes across
  WordPress, Joplin, Notion, and Obsidian. The preview returns surface-specific
  settings, risks, and future adapter steps without provider calls, token
  prompts, note writes, vault writes, post publishing, projection receipts,
  minting, cleanup, or ZET transport.

## v0.3.7 - 2026-06-13

- Added optional `archive objet-capture --project-intake-receipt <receipt>` context validation, and matching selection-manifest support via `project_intake_receipt_path`, so reviewed project-intake decisions can gate capture planning before staged bytes are read; added fake-archive roundtrip regressions for plan -> decisions -> status -> source-intake -> create-draft/mint metadata and plan -> decisions -> status -> source-intake -> objet-capture.
- Added read-only CLI/MCP human artifact store planning for WordPress, Joplin, Notion, Obsidian, Evernote, generic Markdown, and generic workspace surfaces, keeping raw data, human-facing artifacts, and system/AI artifacts separate without provider calls, note writes, publishing, uploads, minting, cleanup, or ZET transport.
- Added read-only MCP `project_intake_plan` and `project_intake_status`, and added `project_intake_receipt` support to MCP `source_intake_plan`, so AI runtimes can follow the human-guided intake question loop without project-intake write/apply tools.
- Added read-only CLI `archive provider-status --dry-run` and MCP `provider_setup_status` to compare setup-managed GitHub/object-storage provider metadata with local provider setup receipts without provider calls, uploads, sync, pushes, or file writes.
- Added per-item `item_status` values to derived-text batch dry-run/apply output so large JSONL captures can distinguish ready, skipped, blocked, and written rows at a glance.
- Added `project-intake-status` `next_review_prompts` for missing checklist ids so AI-assisted intake sessions can ask the next human-review questions without inventing or echoing answer values.
- Clarified the project-intake migration spine from project planning through source-intake, objet-capture, derived-text registration, drafting, minting, and cleanup verification; documented the local-only intent behind collaboration/runtime `.gitignore` guardrails.

## v0.3.6 - 2026-06-13

- Added optional `archive source-intake --project-intake-receipt <receipt>` context validation so one-item metadata dry-runs can carry a reviewed project-intake session receipt without echoing answer text or granting automatic execution authority.
- Added `archive project-intake-status --receipt <receipt> --dry-run` to review checklist coverage and receipt integrity without echoing recorded answer text or authorizing automatic execution.
- Added `archive project-intake-decisions --dry-run|--approve --reviewed-by <actor>` to validate and record human-reviewed project intake checklist answers as a local receipt without echoing answer text or running capture/draft/mint/cleanup steps.
- Extended `archive project-intake-plan --dry-run` with a human review checklist, classification labels, and a draft decision-record template while preserving the no-names/no-bodies privacy boundary.

## v0.3.5 - 2026-06-13

- Added `archive derive-text capture --from-manifest <jsonl>` for dry-run/approved batch registration of already extracted UTF-8 derived text.
- Batch derived-text manifests accept one JSON object per line with `source_object_id`, `text_file`, `derivation_kind`, `tool_name`, `tool_version`, and `review_status`; relative `text_file` paths resolve from the manifest location.
- Added `archive repair-gitignore <archive-root> --dry-run|--approve --reviewed-by <actor>` to append missing WOM-kit safe `.gitignore` patterns without rewriting existing entries.
- Removed private dogfood archive identifiers from public guardrail code and docs, keeping generic live-archive and `*-objets` protections.

## v0.3.4 - 2026-06-13

- Added `archive derive-text capture` for dry-run/approved registration of externally extracted text as provenance-aware derived text records.
- Added `objects/manifests/derived-text.jsonl`, local derived text body storage under `objects/derived-text/sha256/`, approval receipts under `receipts/derived-text-capture/`, doctor/schema validation, and search index ingestion for derived text.
- Standardized the first implemented derived-text vocabulary to `parser`, `ocr`, `asr`, `llm_vision` and `unreviewed`, `human_corrected`.

## v0.3.3 - 2026-06-13

Compatible fixes from v0.3.2 upgrade field feedback:

- CLI output no longer crashes on console encodings that cannot represent a character (e.g. emoji on a Korean Windows cp949 console); unencodable characters are replaced,
- doctor now warns (`zettel_frontmatter_unquoted_timestamp`) when frontmatter contains an unquoted YAML timestamp, with the field path and a quoting hint; `doctor --strict` and `validate` treat it as failing,
- `validate` accepts `--strict` for parity with doctor (validate already fails on warnings unless `--allow-warnings`),
- `staged-cleanup-check` now exits `0` only when the report is both `ok` and `safe_to_cleanup`; unsafe cleanup reports exit `1` while still returning the JSON report,
- `view-zets` now indexes list-valued facets as repeated scalar facet rows, so saved views and ad-hoc scalar filters can match zettels tagged with lists,
- `view-zets` now blocks list-valued filter inputs instead of silently broadening or guessing,
- objet-capture source-intake plan SHA binding now has regression coverage against a real `source-intake --dry-run` producer plan through dry-run and approve,
- added `wom-kit/docs/validation-surface.md` documenting what doctor, validate, preflight, and staged cleanup checks each guarantee.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- no archive migration is required for v0.3.2 users,
- rebuild the disposable search index with `archive index <archive-root>` to pick up list-valued facet indexing for `view-zets`,
- cleanup remains manual; `staged-cleanup-check` never deletes files.

## v0.3.2 - 2026-06-11

Frontmatter migration, redaction hardening, and the local capture spine.

Added:

- CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json`,
- approve-gated `archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json`,
- lossless handling for clean object-shaped `provenance.source` values by relocating them to `source_refs`,
- manual-review blockers for ambiguous or unsafe source values,
- doctor compatibility output and migration hints for legacy frontmatter failures,
- v0.3 zettel-rules guidance for required `provenance` and `visibility` subfields,
- approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` capturing approved staged files into the local content-addressed objet store (`objects/sha256/<2>/<64>`) with manifest records and always-written capture receipts,
- report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run` verifying every staged file is preserved or explicitly deferred before any manual cleanup; fails closed on unenumerable trees and never deletes,
- read-only CLI `archive related-zets <archive-root> --zettel-id <id>` with bidirectional typed-edge traversal (backlinks), depth 1-3, cycle safety, and edge-type filters,
- read-only CLI `archive view-zets <archive-root> --view-id <id> | --facet key=value ...` executing saved-view facet filters from `views/*.yml`,
- typed edges and zettel facets in the disposable search index,
- report-only artifact hygiene checker and six-class file-lifecycle baseline doc,
- an end-to-end test proving the full loop: stage -> capture -> draft -> mint -> cleanup-safe.

Privacy:

- redacted-zettel content suppression is now enforced across search, the on-disk index, `list-zettels`, `read-zettel`, block-header previews, projection previews, related-zets, and view-zets, with regression tests per surface.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- `--dry-run` writes no files anywhere; approve paths rewrite only reviewed targets,
- archives authored from older v0.2-draft rules should run the migration dry-run before strict v0.3 validation,
- the objet-capture write path refuses archives without an explicit sandbox marker,
- run `archive index` once to pick up edges and facets,
- private/live archives, provider sync, staged-original deletion, MCP write tools, ZET transport, and schema redesign are not part of this release.

## v0.3.1 - 2026-06-04

Shared update route preview.

Added:

- CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- service `shared_update_route_preview`,
- read-only route pointers for `delegate`, `attest`, `anchor`, and `none`,
- explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardening so free-form or hostile proposed-action metadata is not echoed as a route,
- public documentation, release note, and work log for the v0.3.1 route-preview boundary.

Compatibility:

- the route-preview command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- the command is dry-run only and writes no files,
- the command reuses `zet_shared_update_record_review_preview` before returning a route pointer,
- MCP exposes no shared-update route write/apply/approve tool for this boundary,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe free-form route metadata are not echoed,
- the route preview does not create real trust, import, acceptance, attestation, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.3.0 - 2026-06-03

Shared update attestation/review write boundary.

Added:

- CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- service `record_shared_update_attestation_review`,
- deterministic local review record and receipt paths under `shared-updates/attestation-reviews/` and `receipts/shared-updates/`,
- replay/overwrite refusal for the same reviewed shared update record,
- rollback if the receipt write fails after the review record write,
- public documentation, release note, and work log for the v0.3.0 first write boundary.

Compatibility:

- the shared-update attestation/review command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- MCP exposes no write/apply sibling tool for this boundary,
- the write reuses `zet_shared_update_record_review_preview` before recording anything,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed or persisted,
- `attest` records only a local human review decision and does not create real trust, import, acceptance, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.2.60 - 2026-06-02

v0.2.x freeze and v0.3.0 entry boundary.

Added:

- public [v0.2.x freeze and v0.3.0 entry boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md),
- release note and public-safe work log for the v0.2.60 checkpoint batch,
- capability matrix updates for the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- focused documentation tests for the freeze/boundary document.

Compatibility:

- no private archive migration is required,
- no product CLI command was added,
- no MCP tool was added,
- no archive service behavior changed,
- no schema changed,
- v0.3.0 is proposed to start with one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write,
- no real ZET transport, key-sharing registry, radio-frequency access creation, mirroring delivery, feed update, trust/import/acceptance/anchor mutation, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queue, worker, DID registry, wallet/key custody, public proof anchoring, blockchain, token, system token, validator governance, payment, staking, consensus, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.59 - 2026-06-02

ZET transport threat model and would-transport plan.

Added:

- CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- MCP `zet_transport_would_plan`,
- read-only service `zet_transport_would_plan`,
- method-specific planning-only risk/control previews for `key-sharing`, `radio-frequency`, and `mirroring`,
- public documentation, release note, and work log for the v0.2.59 planning batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the planner reuses the v0.2.56 single-record review preview policy before producing any plan,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed,
- no real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queues, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.58 - 2026-06-02

ZET shared update record review index.

Added:

- CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_index`,
- read-only service indexing for direct-child local shared update record JSON files,
- public documentation, release note, and work log for the v0.2.58 index batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the index reuses the v0.2.56 single-record review preview policy,
- unsafe records remain blocked per record and record body text is never echoed,
- no shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.57 - 2026-06-02

Capability matrix and README readability patch.

Added:

- public [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md) for implemented, read-only preview, approval-gated write, documented-only, local hygiene, and not-implemented surfaces,
- release note and public-safe work log for the v0.2.57 readability batch,
- focused documentation tests for the capability matrix and README release-tag sequence.

Changed:

- shortened the top-level README status summary and pointed readers to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- recorded a proposed v0.2.x closing plan and a narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

Compatibility:

- no private archive migration is required,
- no archive product CLI, MCP, service, provider, transport, trust/import, attestation/signature, anchor, payment, blockchain, token, worker, or full-auto behavior changed.

## v0.2.56 - 2026-06-02

ZET shared update record review preview.

Added:

- CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_preview`,
- read-only service validation for local archive-contained shared update record JSON before any receiver-side renewal action,
- release note and public-safe work log for the v0.2.56 preview batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the preview reads only the selected archive-relative JSON record,
- unsafe absolute paths, URL-like record paths, body-included records, token/secret-like values, and true mutation/write/transport/provider/trust flags block,
- no shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.55 - 2026-05-27

ZET shared update record baseline.

Added:

- public documentation for a future receiver-side ZET shared update record,
- sanitized non-executable example JSON for a shared update review preview,
- release note and public-safe work log for the v0.2.55 documentation/example batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the example is body-free and contains placeholder refs only,
- no shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.54 - 2026-05-27

Main branch protection readiness baseline.

Added:

- public documentation for staged future `main` branch protection readiness,
- a recommended path from local release-readiness gate to future GitHub Actions, required status checks, and optional review requirements,
- release note and public-safe work log for the v0.2.54 documentation batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Actions, branch protection, repository settings, or GitHub API behavior changed,
- no files are rewritten automatically,
- no external URLs are fetched,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.53 - 2026-05-27

Release readiness gate patch.

Added:

- local `wom-kit/tools/check_release_readiness.py` gate that runs the existing public release hygiene checkers together,
- unit tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documentation, release note, and public-safe work log for the v0.2.53 gate batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the gate runs local subprocess calls to public hygiene checkers only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no GitHub APIs, GitHub Actions, branch protection, product doctor/test commands, providers, private archives, or GitHub Releases are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.52 - 2026-05-27

Public privacy hygiene checker patch.

Added:

- local `wom-kit/tools/check_public_privacy.py` checker for public release and documentation privacy hygiene,
- unit tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholder allowances, current-repository pass behavior, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.52 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known public text files only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no private archives, provider APIs, GitHub Releases, or full-disk locations are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.51 - 2026-05-27

Korean product-language hygiene checker patch.

Added:

- local `wom-kit/tools/check_korean_product_language.py` checker for public Markdown documentation,
- unit tests for required Korean product-language anchors, risky drift phrases, current-facing spelling variants, messenger thread blockchain claims, WordPress/ZET transport claims, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.51 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known Markdown files only,
- no files are rewritten automatically,
- no code identifiers, CLI commands, JSON fields, schema fields, filenames, or package names are renamed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.50 - 2026-05-27

Korean product-language baseline patch.

Added:

- Korean product-language baseline for WOM, zettel-kasten, zet, ZET, objet, lifecycle verbs, block/header/body wording, foreign block safety terms, sharing forms/methods, surface/action terms, SNS-type ZET actions, and messenger-type ZET threads,
- README and public documentation map pointers to the new Korean concept document,
- release note and public-safe work log for the v0.2.50 batch.

Clarified:

- `WOM` is pronounced `옴`, not `웜`,
- `zet` may be explained as `쪽글` or `토막글`, while the product term remains `zet`,
- `ZET` may be explained as `공유 계층`, while the product term remains `ZET`,
- Korean product terms are for public explanation, not CLI/JSON/schema/file/package renames.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no real ZET transport, real trust/import/acceptance/anchor, attestation/signature write, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.49 - 2026-05-27

Public release link hygiene patch.

Added:

- local public-link checker for repository Markdown and release-note link hygiene,
- tests for case-sensitive local Markdown links, release-note relative link rejection, GitHub `blob` link mapping, and suspicious GitHub `tree` file links,
- documentation explaining repo-local Markdown links, GitHub Release body links, external URLs, and case-sensitive public GitHub paths.

Fixed:

- release note links that were correct inside the repository but unsafe when copied into GitHub Release bodies.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Release was edited by the tool,
- no network URL fetching, provider calls, WordPress publishing, projection writes, receipts, ZET transport, recommendation fetching/ranking, neighbor feed updates, trust/import/acceptance/attestation/signature/minting changes, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.48 - 2026-05-27

ZET radio-frequency recommendation model baseline patch.

Added:

- documentation for the future distinction between followed/neighbor feeds and recommended/broadcast feeds,
- documentation for the radio-frequency metaphor where a node tunes into an accessible ZET channel, frequency, scope, or broadcast lane,
- documentation for prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles rather than only LLM prompts,
- sanitized non-executable selector shape example with central black-box ranking disabled.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- no recommendation fetching, ranking, feed update, provider call, WordPress publishing, projection write, receipt write, ZET transport, trust, import, acceptance, attestation, signature, minting, anchoring, delegation, payment, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.47 - 2026-05-26

ZET closed sharing model baseline patch.

Added:

- documentation for the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documentation for the unit layer distinction between `zet` and `objet`,
- documentation for the future ZET closed sharing/SNS layer above the base system,
- documentation for pluggable user-selected surfaces such as custom SaaS, open-source ZET UI, static site, private archive UI, feed/RSS-like app, team workspace, WordPress, or future dedicated ZET client,
- sanitized non-executable example shape for a future closed sharing update.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- GitHub is clarified as base infrastructure or possible substrate, not the whole ZET sharing architecture,
- WordPress is clarified as one possible projection surface, not the WOM/ZET UI,
- attestation is described as receiver-side verification/review before any future neighbor feed update, mirror, or re-projection,
- this release does not call providers, publish to WordPress, write projection records or receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.46 - 2026-05-26

ZET projection plan dry-run preview patch.

Added:

- `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- read-only MCP `zet_projection_plan_check`,
- metadata-only projection plan output for one local zet and one operator-declared surface kind,
- closed safety flags for provider, WordPress, projection-write, receipt-write, trust, import, acceptance, attestation, signature, mint, ZET transport, and full-auto behavior.

Compatibility:

- no private archive migration is required,
- the preview writes nothing and returns `would_change: []`,
- it does not output the full zet body,
- it uses archive-relative paths only,
- visibility is operator-declared intent, not verified provider state,
- projection format is future intent, not rendered body output,
- this release does not call providers, publish to WordPress, write projection records or receipts, mint, trust, import, accept, attest, sign, anchor, apply, run ZET transport, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.45 - 2026-05-26

ZET publication surface baseline patch.

Added:

- documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- release notes and work log for the ZET publication surface baseline.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- posting is documented as separate from minting,
- a surface locator is documented as separate from canonical zet identity,
- the examples use placeholder identifiers and `https://example.invalid/...` only,
- this release does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## v0.2.44 - 2026-05-26

Foreign block attestation statement draft decision preview patch.

Added:

- `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- non-binding route previews for `keep_under_review`, `revise_statement_draft`, `reject_statement_draft`, `prepare_future_attestation_statement_review`, and `needs_more_review`,
- current statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt consistency checks before any route preview.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the default route intent is `needs_more_review`,
- review notes are preview context only; raw note bodies are not echoed or stored,
- previewed statement drafts remain `untrusted_foreign`, with `decision_status: preview_not_recorded`, `attestation_status: not_created`, and `signature_status: not_created`,
- the decision preview does not create trust, import, acceptance, attestation, signatures, minting, sharing, WordPress publishing, provider calls, ZET transport, receipts, or apply behavior,
- MCP remains read-only and exposes no statement draft decision write/apply/accept, foreign block attest/sign/trust/import, provider sync, WordPress publishing, mint, anchor, or full-auto tool.

## v0.2.43 - 2026-05-26

Foreign block attestation statement draft review index patch.

Added:

- `archive attestation-statement-draft-review <archive-root> --format json`,
- optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- index validation for recorded untrusted attestation statement drafts and matching draft receipts,
- current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed style/scope filters do not hide blockers from other discovered statement draft records,
- `--case-id` scopes the consistency verdict to one case,
- indexed records remain `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- indexing a statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft review apply/write/approve, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.42 - 2026-05-26

Foreign block attestation statement draft write approval patch.

Added:

- `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <safe-actor-id>` to record a local statement draft record and matching receipt,
- read-only MCP `record_attestation_statement_draft_check`,
- stale/tamper checks that treat the v0.2.41 draft preview JSON as untrusted input and revalidate current candidate, receipt, quarantine, and decision state before any write,
- rollback-safe exclusive creation for exactly two files: `attestation-statement-draft.json` and its quarantine receipt.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one statement draft record plus one receipt,
- approved records stay `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- recording the statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft approve/write/apply, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.41 - 2026-05-26

Foreign block attestation statement draft preview patch.

Added:

- `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_preview`,
- non-binding statement draft output for one recorded attestation review candidate,
- validation that re-reads the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before returning a draft.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the statement draft is not an attestation, not trust, not signing, not import, not minting, not a receipt write, and not ZET transport,
- hash commitments remain `not_verified`, `not_trusted`, and not proof of authenticity,
- MCP remains read-only and exposes no statement draft write/apply, foreign block attest/sign/trust/import/accept, receipt-write, full-auto, provider, or ZET transport tool.

## v0.2.40 - 2026-05-26

Foreign block attestation review candidate index patch.

Added:

- `archive attestation-candidate-review <archive-root> --format json`,
- optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_review_candidate_index`,
- index validation for recorded untrusted attestation review candidates and matching candidate receipts,
- current quarantine case, original quarantine receipt, recorded decision, and decision receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed filters do not hide blockers from other discovered candidate records,
- indexed candidates remain `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- indexing a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no candidate review approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.39 - 2026-05-25

Foreign block attestation review candidate write approval patch.

Added:

- `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <actor-id>` to record an untrusted attestation review candidate,
- optional replay guards for expected case id, review scope, and prospective attestor,
- read-only MCP `record_attestation_review_candidate_check`.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one candidate record plus one receipt,
- approved records stay `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- recording a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, or acceptance,
- MCP remains read-only and exposes no candidate approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.38 - 2026-05-25

Foreign block attestation review candidate plan patch.

Added:

- `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- read-only MCP `foreign_block_attestation_review_candidate_plan`,
- a human-review candidate object for cases whose recorded decision is `eligible_for_attestation_review` and whose planned outcome is `prepare_attestation_review_candidate`.

Compatibility:

- no private archive migration is required,
- candidate planning writes nothing and never reads the original foreign artifact, source payloads, objet bodies, or provider URLs,
- all candidates remain `untrusted_foreign`, `planned_not_recorded`, and `not_created`,
- hashes in existing sanitized records are retained only as commitments or claims, not proof of authenticity,
- MCP remains read-only and exposes no candidate apply/write/accept/trust/import/attest/sign/mint/full-auto tool.

## v0.2.37 - 2026-05-25

Foreign block decision outcome plan patch.

Added:

- `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_decision_outcome_plan`,
- conservative outcome routing for recorded quarantine decisions.

Compatibility:

- no private archive migration is required,
- outcome planning writes nothing and never reads the original foreign artifact,
- all outcomes remain `untrusted_foreign` and `planned_not_applied`,
- `eligible_for_attestation_review` only becomes `prepare_attestation_review_candidate`; it does not create trust or an attestation,
- MCP remains read-only and exposes no outcome apply/write/accept/trust/import/attest/mint/full-auto tool.

## v0.2.36 - 2026-05-25

Foreign block quarantine decision review index patch.

Added:

- `archive quarantine-decision-review <archive-root> --format json`,
- optional `--case-id`, `--decision`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_decision_review_index`,
- consistency checks for recorded quarantine decision records and matching decision receipts,
- current quarantine case and original quarantine receipt checks when reviewing recorded decisions.

Compatibility:

- no private archive migration is required,
- the decision review index writes nothing and never reads the original foreign artifact,
- indexed decisions remain `untrusted_foreign` review records only,
- MCP remains read-only and exposes no quarantine decision review apply/write/accept/import/trust/attest/full-auto tool.

## v0.2.35 - 2026-05-25

Foreign block quarantine decision write approval patch.

Added:

- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine decision records under `quarantine/foreign-blocks/<case-id>/quarantine-decision.json`,
- quarantine decision receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`,
- read-only MCP `record_quarantine_decision_check` for dry-run validation only,
- replay validation that re-reads the current quarantine case and receipt before any approved local decision record write.

Compatibility:

- no private archive migration is required,
- decision writes are local review records only; they never trust, import, mint, attest, anchor, delegate, sign, execute, accept, apply, share, or call providers,
- approved writes are limited to the sanitized quarantine decision JSON and quarantine decision receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine decision apply/write/import/trust/attest/accept/full-auto tool.

## v0.2.34 - 2026-05-25

Foreign block quarantine decision preview patch.

Added:

- `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- optional preview context: `--decision-intent`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_quarantine_decision_check`,
- decision-path previews for existing untrusted quarantine cases: `keep_quarantined`, `reject_and_keep_record`, `eligible_for_attestation_review`, and `needs_more_review`.

Compatibility:

- no private archive migration is required,
- quarantine decision preview writes nothing and never reads the original foreign artifact,
- decision preview does not record approval, trust, import, attestation, minting, anchoring, delegation, signing, acceptance, or apply state,
- MCP remains read-only and exposes no quarantine decision apply/write/import/trust/attest tool.

## v0.2.33 - 2026-05-25

Foreign block quarantine review index patch.

Added:

- `archive quarantine-review <archive-root> --format json`,
- optional `--case-id`, `--status`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_review_index`,
- inventory and consistency checks for `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- matching quarantine write receipt checks under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Compatibility:

- no private archive migration is required,
- quarantine review index writes nothing and never reads the original foreign artifact,
- indexing does not mean reviewed, trusted, imported, attested, minted, anchored, delegated, signed, or accepted,
- MCP remains read-only and exposes no quarantine review apply/import/trust/attest/write tool.

## v0.2.32 - 2026-05-25

Foreign block quarantine write approval patch.

Added:

- `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine case writes under `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- quarantine write receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`,
- read-only MCP `quarantine_foreign_block_check` for dry-run validation only,
- validation for v0.2.31 `foreign_block_quarantine_plan` reports before any approved local write.

Compatibility:

- no private archive migration is required,
- quarantine write is an isolation record only; it does not trust, import, mint, attest, anchor, delegate, sign, or execute the foreign block,
- approved writes are limited to the sanitized quarantine case JSON and quarantine write receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine apply/write/import/trust/attest/full-auto tool.

## v0.2.31 - 2026-05-25

Foreign block quarantine plan patch.

Added:

- `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_quarantine_plan`,
- validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write,
- structured quarantine actions: `blocked`, `hold_for_human_review`, and `ready_for_future_quarantine_write`,
- preview-only archive-relative quarantine paths under `quarantine/foreign-blocks/<case-id>/...` that are not created.

Compatibility:

- no private archive migration is required,
- quarantine plan writes nothing and never reads the original foreign artifact,
- `ready_for_future_quarantine_write` is not trust, not import, not approval, and not a quarantine write; it only means a future explicit quarantine-write workflow could be presented to a human/operator,
- no real quarantine write, trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.30 - 2026-05-25

Foreign block attestation packet preview patch.

Added:

- `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_attestation_packet_check`,
- validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review,
- structured packet status values: `blocked`, `manual_review_required`, and `ready_for_human_attestation_review`,
- attestation packet previews that keep `would_attest: false`, `attestation_status: not_created`, `trust_state: untrusted_foreign`, and `would_change: []`.

Compatibility:

- no private archive migration is required,
- attestation packet preview writes nothing and never reads the original foreign artifact,
- `ready_for_human_attestation_review` is not trust, not an attestation, and not approval; it only means the trust report is clean enough to present for a future explicit human review,
- no real trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.29 - 2026-05-25

Foreign block trust / attestation preview patch.

Added:

- `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_trust_check`,
- validation for v0.2.28 `foreign_block_intake` reports before any future trust/attestation workflow,
- structured `proposed_trust_action` values: `reject`, `manual_review_required`, and `eligible_for_future_attestation`,
- hash, reference, and prompt-boundary assessments that keep every foreign block `untrusted_foreign`.

Compatibility:

- no private archive migration is required,
- trust preview writes nothing and always returns `would_change: []`,
- `eligible_for_future_attestation` is not trust; it only means the report is clean enough for a future explicit attestation workflow,
- no real trust/apply/import, attestation write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.28 - 2026-05-25

Foreign block intake preview patch.

Added:

- `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_intake_check`,
- conservative intake for foreign block-header JSON artifacts and Markdown-compatible foreign zets,
- claimed hash summaries that are explicitly `not_verified`,
- prompt-boundary recommendations for foreign text,
- public docs for foreign block intake.

Compatibility:

- no private archive migration is required,
- foreign block intake writes nothing and always returns `would_change: []`,
- foreign text can inform, but cannot command,
- foreign blocks remain `untrusted_foreign` until a future attest/check path exists,
- no real ZET transport, import/apply, draft creation from foreign content, automatic trust, real signing, payment, staking, consensus, blockchain, provider sync, OCR, or LLM classification is implemented.

## v0.2.27 - 2026-05-25

Prompt boundary draft composer patch.

Added:

- `archive create-draft --prompt-boundary-report <json-file>`,
- validation that prompt-boundary reports are dry-run-only, non-mutating, and preserve the untrusted-text boundary before draft composition,
- optional draft frontmatter `prompt_boundary` metadata with report hash, risk level, source kind/path summary, detected pattern ids, and handling note,
- MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--prompt-boundary-report` is omitted,
- low prompt-boundary risk is recorded as heuristic context, not proof of safety,
- medium risk is allowed with warnings,
- high risk blocks draft creation,
- no LLM classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior is implemented.

## v0.2.26 - 2026-05-25

Prompt injection boundary, responsible use, and runtime model guidance baseline.

Added:

- `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- read-only MCP `prompt_boundary_check`,
- conservative prompt-injection and unsafe-agent string heuristics,
- public prompt injection boundary, responsible use, disclaimer, and runtime model guidance docs.

Compatibility:

- no private archive migration is required,
- prompt-boundary is read-only and writes nothing,
- the check does not call LLMs, provider APIs, web browsing, OCR, import apply, or ZET transport,
- this is not a complete prompt-injection classifier or legal advice,
- HITL remains the recommended default and full-auto operation remains advanced/experimental operator responsibility.

## v0.2.25 - 2026-05-25

Profile wallet concept baseline.

Added:

- `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- read-only MCP `wom_profile_wallet_check`,
- optional public-safe `node` and `wallet` metadata fields for WOM profile registry entries,
- documentation for the wallet-ready identity model: WOM profile selects the human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can sign capability/proof actions.

Compatibility:

- no private archive migration is required,
- existing profile registry entries remain valid,
- no private key generation, real cryptographic signing, blockchain API call, provider API call, wallet registration, token storage, seed phrase storage, payment layer, staking layer, consensus, ledger, or P2P transport is implemented,
- WOM profile is not a crypto wallet in v0.2.25; it is a wallet-ready identity model.

## v0.2.24 - 2026-05-25

Block header preview patch.

Added:

- `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- read-only header derivation for `block = zet + header`,
- deterministic `zet_body_sha256`, `header_sha256`, and `block_hash_preview`,
- referenced zet, objet, and receipt summaries from frontmatter metadata,
- read-only MCP `block_header_check`.

Compatibility:

- no private archive migration is required,
- no zets are modified,
- no minting or receipt writing is performed,
- no referenced objet/source file body is read or hashed,
- no provider URL is followed and no provider API is called,
- ZET remains the sharing layer; the product term is `block`, not a ZET-prefixed block term.

## v0.2.23 - 2026-05-25

Source intake draft composer patch.

Added:

- `archive create-draft --source-intake-plan <json-file>` for consuming a v0.2.22 `source-intake --dry-run --format json` result,
- validation that source intake plans are dry-run-only, blocker-free, metadata-only, and safe before refs are merged into draft frontmatter,
- optional `source_intake` draft frontmatter metadata with a plan hash, source/objet status summary, object storage flag, and content access proof,
- MCP `create_draft_zettel` support for a structured `source_intake_plan` object,
- mint receipt previews and receipts preserve `source_refs` and `source_intake` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--source-intake-plan` is omitted,
- the source intake plan file path is not stored in draft frontmatter,
- no source intake apply, objet capture, file copy/upload/import/OCR/transcription/full hashing/provider API call, automatic minting, or MCP real minting is implemented.

## v0.2.22 - 2026-05-25

Source intake planner patch.

Added:

- `archive source-intake <archive-root> --dry-run --format json`, a dry-run-only planner for classifying source/objet references before draft creation,
- locator support for local files, source map items, source-relative paths, `objet:sha256:...`, technical `object_id`, provider object refs, and AI artifact refs,
- stable source intake JSON with draft-ready `source_refs_for_draft`, objet status, object storage context, content access flags, blockers, warnings, and next safe actions,
- object storage context reporting from `provider-bindings.yml`,
- read-only MCP `source_intake_plan`.

Compatibility:

- no private archive migration is required,
- source intake writes nothing,
- no file body is read and no full SHA-256 is calculated,
- no copy, upload, import, OCR, transcription, parser extraction, provider API call, automatic draft creation, mint, or provider sync is implemented,
- MCP exposes no source intake apply/capture/upload/sync/provider API tool.

## v0.2.21 - 2026-05-25

Object storage / objet setup planner patch.

Added:

- `archive object-storage <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped objet storage setup,
- safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- default objet prefix planning as `archives/<archive_id>/objets/`,
- strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a bucket/container,
- optional ignored local object storage account hints with `--write-local-profile`,
- read-only MCP `object_storage_setup_plan`.

Compatibility:

- no bucket/container is created,
- no OAuth, provider API, upload, sync, source copy, file hashing, or source import operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no object storage apply/create/connect/upload/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.20 - 2026-05-25

GitHub profile repository setup planner patch.

Added:

- `archive github-repo <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped GitHub repository setup,
- safe default repository naming as `zettel-kasten-<profile_slug>`,
- strict profile slug and repository name safety gates for ASCII-only, path-free, URL-free, secret-free values,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a GitHub repository,
- optional ignored local account hints with `--write-local-profile`,
- read-only MCP `github_repository_setup_plan`.

Compatibility:

- no GitHub repository is created,
- no OAuth, GitHub API, `gh`, `git remote`, push, or sync operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no GitHub apply/create/connect/push/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.19 - 2026-05-25

WOM-kit naming and path cleanup patch.

Added:

- renamed the implementation folder from the old placeholder path to `wom-kit/`,
- renamed the Python import package to `wom_kit`,
- changed package metadata to `wom-kit`,
- kept compatibility console scripts `archive` and `archive-mcp`,
- added preferred console script aliases `wom` and `wom-mcp`,
- updated current-facing docs, CLI/MCP docs, schema titles, examples, tests, and wrapper scripts to use `WOM-kit`, `wom-kit`, and `wom_kit` by context.

Compatibility:

- repository root remains `zettel-kasten`,
- command behavior is unchanged,
- lifecycle commands remain available,
- the old package/folder names are not current product names,
- this release does not add source-intake, GitHub repo creation, provider sync, UI, or any change to WOM/zet/ZET philosophy.

## v0.2.18 - 2026-05-24

Profile-aware draft zet creation dry-run patch.

Added:

- `archive create-draft --dry-run`, a no-write preview for inbox draft zet creation,
- replay-safe draft fields: `--draft-id`, `--created-at`, `--expected-body-sha256`, and `--draft-approved-by`,
- profile-aware draft context flags for resolved profile id, operator id, authority mode, expected archive id, and expected archive type,
- optional draft provenance fields for creation mode, assisting actors, supervising actors, derived refs, source refs, local AI sessions, and inbox-draft-only approval metadata,
- MCP `create_draft_zettel` dry-run support with the same profile-aware provenance inputs,
- safety gates that block archive id/type mismatch, body hash mismatch, empty body content, malformed deterministic timestamps, unsafe local paths, provider storage locators, and secret-like values,
- line-ending-normalized body hashes so LF/CRLF differences do not break approved draft replay,
- AI-assisted and AI-generated draft gates that require the assisting AI runtime to be identified,
- mint receipt propagation for draft `source_refs`, `provenance.derived_from`, and `local_ai_sessions`.

Compatibility:

- existing `create-draft` usage remains compatible when the new flags are omitted,
- dry-run writes nothing,
- real draft creation still writes only to `inbox/`,
- profile-bound AI draft writes require draft approval and expected body hash replay values,
- minting remains a separate CLI approval step and MCP still exposes no real mint tool.

## v0.2.17 - 2026-05-24

WOM Profile Registry dry-run patch.

Added:

- `archive profile-list --registry <path> --format json`, a read-only CLI command that lists local WOM profile registry entries with local paths redacted by default,
- `archive profile-resolve --registry <path> --target <query> --format json`, a read-only CLI command that resolves a requested profile by exact profile id, label, or alias before runtime context or draft work,
- read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- token-state aware resolution so a missing token can still resolve profile identity while disabling direct write availability,
- delegate fallback previews when a target profile is missing or a matched profile has no usable token,
- an example profile registry template with placeholder paths and fake `token_ref` values only,
- Unicode-normalized matching and blockers for registry version drift, duplicate profile ids, and raw token-like fields.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- profile registry commands never write files, never scan the whole disk, never store tokens, and do not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

## v0.2.16 - 2026-05-24

WOM AI Runtime Context Layer patch.

Added:

- `archive runtime-context <archive-root> --format json`, a read-only CLI command for terminal-capable AI runtimes to confirm archive identity, type/scope, owner/principal summary, AI write policy, safe archive-relative paths, safe next actions, and doctor summary before drafting or asking for mint approval,
- default local path redaction for runtime context JSON, with `--no-redact-local-paths` available only for trusted local debugging,
- `--expected-archive-id`, `--expected-type`, and `--strict` gates so the runtime can block on archive id mismatches and treat archive type mismatches as warning-by-default or blocking in strict mode,
- read-only MCP tool `archive_runtime_context` with the same core behavior and existing MCP allowed-root enforcement,
- stable runtime context summary keys for AI parsing, with unavailable optional values represented as `null`,
- MCP local path disclosure gating through `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1`.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- runtime context never writes files and does not implement create-draft dry-run, provider API sync, UI, real minting through MCP, or any new MCP apply tool.

## v0.2.15 - 2026-05-23

WOM Safe HTML Profile validator dry-run patch.

Added:

- `archive check-safe-html --path <zet> --dry-run` CLI command, a read-only validator that inspects a v0.2 Markdown-compatible zet and reports whether it is compatible with a future WOM Safe HTML Profile migration,
- block detection for `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, and inline event handler attributes (for example `onclick=`),
- structured JSON output with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

Compatibility:

- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- the validator only reads; it never writes files, never converts Markdown to HTML, never changes mint output, and never migrates existing zets,
- the WOM Safe HTML Profile element/attribute allowlist is still not finalized; the validator only flags obviously unsafe patterns at this stage,
- no private archive migration is required.

## v0.2.14 - 2026-05-23

WOM Safe HTML Profile documentation/spec baseline patch.

Added:

- WOM Safe HTML Profile documents in English and Korean,
- public distinction between `WOM`, `zet`, and `ZET`,
- documentation that keeps Markdown as an authoring/import compatibility format while setting WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- stronger explanation that `ZET` is the communication layer that can become messaging, SNS/feed, or collaboration.

Compatibility:

- no private archive migration is required,
- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- no Markdown-to-HTML converter, validator, UI, live sharing, or P2P transport is implemented in this release.

## v0.2.13 - 2026-05-23

WOM naming baseline and compatibility alias patch.

Added:

- public WOM naming documents in English and Korean,
- `mint-zet` as the preferred CLI surface for minting a zet, with `mint-zettel` preserved as a compatibility alias,
- `parcel` as the preferred CLI surface for creating a portable bounded unit, with `pack` preserved as a compatibility alias,
- `admit --dry-run` as the preferred CLI surface for previewing parcel/workpack admission, with `import --dry-run` preserved as a compatibility alias,
- documentation that places `WOM`, `zet`, `node`, and `mint -> delegate -> attest -> anchor` at the center of the product language.

Compatibility:

- `wom-kit`, `zettels/`, `receipts/`, `workpacks/`, and existing schema names remain unchanged for v0.2 compatibility,
- `promote`, `share`, `mint-zettel`, `pack`, and `import` remain available,
- no private archive migration is required.

## v0.2.12 - 2026-05-23

Real delegate receipt write patch.

Added:

- `delegate-zet --approve --reviewed-by <actor>` for writing a schema-backed delegate receipt,
- `receipts/delegate/*.delegate.json` doctor validation,
- real delegate capability nonce issuance with receipt-local claim/spent state,
- duplicate delegate receipt protection through dry-run blockers and exclusive file creation.

Compatibility:

- `delegate-zet --dry-run` remains the preview gate,
- MCP delegate tooling remains read-only and dry-run only,
- no real claim registry, spent registry, revocation registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.11 - 2026-05-23

Delegate capability contract patch.

Added:

- `delegate-zet --target-policy counterparty_bound|claimable_once`,
- `claimable_once` delegate previews that can defer the recipient archive until attestation,
- `delegation_capability` preview fields for capability id, claim/spent preview state, nonce placeholder, binding method, and settlement condition,
- `claim_binding` previews in attestation and anchor metadata,
- MCP parity for `delegate_zet_check` with optional `target_archive`.

Compatibility:

- existing `delegate-zet` and `share --dry-run` flows remain compatible,
- v0.2.10 delegate receipts without capability fields are treated as legacy `counterparty_bound`,
- no real claim registry, spent registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.10 - 2026-05-23

ZET sharing dry-run lifecycle contract.

Added:

- `delegate-zet --dry-run` as the product-facing dry-run surface for scoped zet delegation,
- `attest-zet --dry-run` for verifying a delegated foreign zet receipt without writing files,
- `anchor-zet --dry-run` for previewing local meaning-network anchoring without writing files,
- read-only MCP tools `delegate_zet_check`, `attest_zet_check`, and `anchor_zet_check`,
- schemas for delegate receipts, attestation receipts, and anchor metadata.

Compatibility:

- existing `share --dry-run` and MCP `share_check` remain available,
- no real P2P, SNS/feed, transport, external sending, or foreign zet import is implemented,
- no private archive migration is required.

## v0.2.9 - 2026-05-23

Terminology stabilization patch.

Changed:

- made `mint` the preferred product language for current CLI and user-facing docs,
- changed newly initialized archives to use `ai_write_policy.canonical_requires: human_minting`,
- kept `human_promotion` valid for legacy archives without doctor warnings,
- added optional `minting_rules` to zettel rules while keeping `promotion_rules` for v0.2 compatibility,
- made mint dry-runs prefer `minting_rules` and fall back to legacy `promotion_rules`,
- kept `promote`, `promotion_check`, `promotion` frontmatter, and old promotion receipts as compatibility surfaces.

Migration:

- no private archive migration required,
- existing archives that still use `human_promotion` remain valid,
- new archives should use `human_minting`.

## v0.2.8 - 2026-05-23

Minting lifecycle implementation.

Added:

- `mint-zettel` CLI command for `draft zet -> canonical private zet -> mint receipt -> draft snapshot`,
- mint receipt schema at `schemas/mint-receipt.schema.json`,
- canonical zettel `mint` frontmatter metadata with `authority_mode: basic`,
- `receipts/mint/*.mint.json` and `receipts/mint/drafts/*.draft.md` validation in doctor,
- read-only MCP `mint_zettel_check` dry-run tool.

Changed:

- real minting preserves the original `inbox/` draft,
- real minting snapshots the exact draft text at mint time,
- canonical zettels may now satisfy doctor lifecycle metadata with either new `mint` metadata or legacy `promotion` metadata,
- `promote` remains available as a compatibility command.

Migration:

- no private archive migration required,
- archives that use `mint-zettel` should keep the generated mint receipts and draft snapshots under `receipts/mint/`.

## v0.2.7 - 2026-05-23

Foundational product whitepaper patch.

Added:

- detailed English foundational product whitepaper,
- detailed Korean foundational product whitepaper,
- public-safe product whitepaper depth correction work log.

Clarified:

- `zettel-kasten` is memory infrastructure, not only a note app,
- `zet` is always text and functions as interpreted archive memory,
- minting means private archive issuance, not posting or sharing,
- the same authority model supports HITL workflows and scoped AI-agent harnesses,
- object storage covers source/original documents as well as media,
- Notion, Google Drive, local folders, GitHub, object storage, and external URLs should be handled through provenance-aware provider bindings,
- `zet` sharing can project into messenger, SNS/feed, or collaboration workspace behavior depending on relationship topology,
- the Web3-like property is subject-owned, portable, verifiable memory rather than token hype.

Migration:

- no private archive migration required.

## v0.2.6 - 2026-05-23

README baseline display correction.

Changed:

- updated the English README current public baseline from `v0.2.5` to `v0.2.6`,
- updated the Korean README current public baseline from `v0.2.5` to `v0.2.6`,
- aligned package and citation metadata with the new public patch release.

Why:

- `v0.2.5` correctly published the documentation map and philosophy patch, but the public repository page needed a follow-up patch so the visible README baseline and release chain stayed consistent without moving an already-published tag.

Migration:

- no private archive migration required.

## v0.2.5 - 2026-05-23

Public documentation map and philosophy patch.

Added:

- public documentation map,
- Korean public documentation map,
- product philosophy document,
- Korean product philosophy document.

Clarified:

- public records are separated into product blueprint/design philosophy, implementation reference research, implementation plans, and work logs,
- the project philosophy includes human data primitives, AX rationale, and Web3-like `zet` sharing,
- README files now link directly to those document groups.

Migration:

- no private archive migration required.

## v0.2.4 - 2026-05-23

Documentation polish patch.

Added:

- `README.ko.md` as a full Korean project entrypoint,
- `UPGRADE.ko.md` as a Korean upgrade guide,
- `v0.2.4` release note.

Changed:

- rewrote `README.md` as a cleaner English public entrypoint,
- split bilingual explanations into separate English/Korean documents,
- clarified public status, storage model, text provenance, versioning, and privacy boundaries.

Migration:

- no private archive migration required.

## v0.2.3 - 2026-05-23

Bilingual documentation patch.

Added:

- Korean summary in `README.md`,
- Korean upgrade guidance in `UPGRADE.md`,
- Korean notes in the `v0.2.3` release note.

Migration:

- no private archive migration required.

## v0.2.2 - 2026-05-23

Public history hygiene and text provenance clarification.

Added:

- text provenance hierarchy documentation,
- clearer distinction between original editable text, parser-extracted text, OCR/AI transcription, human-reviewed derived text, and minted zets.

Clarified:

- OCR and AI transcription should be stored, but as model-dependent derived text records,
- born-digital editable text has higher evidence authority than OCR-derived text,
- derived text must keep provenance to the source object and tool/model that produced it.

Repository hygiene:

- public history should be rewritten so older public commits do not remain as normal refs with local/private-looking examples.

Migration:

- no private archive migration required,
- future derived-text schemas may require a migration once implemented.

## v0.2.1 - 2026-05-23

Public documentation and repository hygiene patch.

Added:

- `UPGRADE.md`,
- per-version release notes under `wom-kit/docs/releases/`,
- clearer version compatibility guidance,
- neutralized public examples that looked too close to local/private context.

Clarified:

- document files such as `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, and `.csv` can be source/original objects,
- object storage is the warehouse for original source files, not only media files,
- minted zets remain text and belong in the zettel layer.

Migration:

- no private archive migration required from `v0.2.0`.

## v0.2.0 - 2026-05-23

Initial public showcase baseline.

Includes:

- local-first archive protocol documents,
- zettel and zettel-kasten specs,
- JSON schemas,
- fake sample archive,
- early Python CLI and MCP tooling,
- setup and security docs,
- public product blueprint for `zettel-kasten` and `zet`,
- versioning and compatibility policy,
- source object storage policy for document files and media files.

Notes:

- This is not a production-stable `v1.0.0` release.
- The future `zet` sharing service is not implemented yet.
- Real private archives should not be pushed to the public repository.
