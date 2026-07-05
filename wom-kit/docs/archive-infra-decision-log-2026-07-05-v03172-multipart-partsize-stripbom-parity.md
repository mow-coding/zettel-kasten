# Decision Log — v0.3.172 Live-Multipart Part-Size Override + Strip-BOM Dry-Run Parity

Date: 2026-07-05
Batch: v0.3.172 (implements the LOCKED spec "Two verification-honesty fixes:
live-multipart part-size override + strip-bom dry-run parity").
Anchor tree at spec authoring: HEAD `c764fc93` (v0.3.171), tree clean.
Release action: working tree only — no git commit/tag/push. Never touches a real
archive or `C:\Users\mylifeisbusy\zettel-kasten-basoon`; all archive fixtures live
in temp dirs, and no test opens a real socket (the injected
`_FakeObjectStorageTransport` proves the multipart envelope).

Per the AGENTS.md decision-log mandate this records each substantial decision with the
grounded fact that drove it.

## Item 1 — live-multipart part-size override

- **Flag-naming resolution.** The existing shipped flag is `--multipart-threshold`
  (dest `multipart_threshold`, metavar `BYTES`), not the `--multipart-threshold-bytes`
  the base prose named. The new flag matches the sibling's no-suffix, `BYTES`-metavar
  style: `--multipart-part-size` (dest `multipart_part_size`) plus `--allow-tiny-parts`
  (store_true). No rename of the existing flag; additive and style-consistent.
  — *Rationale: docs must name the real symbol, and the two flags must compose
  consistently.*

- **4 KiB minimum.** New constant `OBJECT_STORAGE_MULTIPART_MIN_PART_SIZE_BYTES = 4096`.
  — *Rationale: a sane concrete floor well above zero that keeps `part_count` bounded
  under `OBJECT_STORAGE_TOTAL_PUT_CEILING` for a small verification fixture.*

- **`--allow-tiny-parts` acknowledgment gate.** A part size below the 64 MiB default is
  refused unless `--allow-tiny-parts` is set, and the blocker states the R2 reality
  (real R2 rejects multipart parts < 5 MiB except the last). — *Rationale: an
  acknowledgment gate so a tiny part size cannot be set accidentally, and so a live
  tiny-part rejection is read as an upload rejection, not an integrity flaw.*

- **Threshold-floor re-basing (load-bearing).** When a part size is supplied and valid,
  the `--multipart-threshold` floor is compared against `effective_multipart_part_size_bytes`,
  not the 64 MiB module constant, and the blocker text interpolates the effective value.
  — *Rationale: to force multipart on a small object an operator lowers BOTH the
  threshold and the part size; if the floor still referenced 64 MiB the threshold could
  never drop below it and `is_multipart` would never be true — the feature dead on
  arrival. The part-size validation is evaluated BEFORE the threshold block so the
  effective part size is known when the floor is checked.*

- **Explicit-threshold pairing.** `--multipart-part-size` does NOT silently auto-lower
  the threshold; the operator sets both flags together, and the validator now permits
  the lowered threshold down to the new part size. — *Rationale: keeps the threshold an
  explicit, receipt-recorded operator choice.*

- **Receipt field addition.** The execution receipt gains
  `effective_multipart_part_size_bytes` (schema property added; non-breaking because the
  schema has no `additionalProperties:false` and does not list it in `required`).
  — *Rationale: `part_count` alone proves a split happened but not the granularity;
  recording the part size lets an auditor verify `ceil(size/part_size) == part_count`
  and prove the split was forced.*

- **Ceiling unchanged.** `put_calls += 1 + max(1, part_count) + 1` and
  `OBJECT_STORAGE_TOTAL_PUT_CEILING = 64` are untouched. The 4 KiB minimum plus a small
  verification fixture keep `part_count` well under 64. — *Rationale: the cost ceiling is
  a guard we must not weaken; the fix is to bound the fixture, not raise the ceiling.*

- **Integrity preserved, confirmed not weakened.** The only executor change is passing
  `part_size_bytes` into `handle.read()`. The whole-object before-hash, the full-object
  sha256 handed to `complete_multipart`, the HEAD-after full-object verify, SA-5
  delete-on-mismatch, and the §6 leak gate are byte-for-byte as shipped. No per-part-hash
  acceptance path, no HEAD-after short-circuit, no part-size-keyed integrity branch.

## Item 2 — strip-bom dry-run parity

- **Classifier-no-op decision.** `strip_bom` in `remint_reconcile_plan` /
  `retire_draft_reconcile_plan` affects ONLY previewed strip-intent metadata
  (`bom_stripped`, `bom_strip_note`); it never touches the Tier A/B/C classifier.
  — *Rationale: the classifier is already BOM-insensitive (`utf-8-sig` read +
  `bytes_normalized_for_content_compare`); re-reading the canonical through any new
  comparison path would bypass the frontmatter/body identity proofs — the exact
  laundering vector. `drift_class` and `content_change_ack_required` are identical
  whether `strip_bom` is True or False, for every file.*

- **Metadata modeling rule.** The plan reads the canonical raw bytes once and checks the
  3-byte BOM prefix: present → preview would-strip; absent → documented no-op preview
  ("no leading BOM present; nothing stripped"), never a previewed byte rewrite. When
  `strip_bom` is False the preview fields are omitted (unchanged behavior).

- **Both-surface scope.** Fix `retire-draft-reconcile` symmetrically, not just remint —
  it has the identical dry-run(no strip_bom)/apply(strip_bom) asymmetry and `--strip-bom`
  is registered on both parsers. — *Rationale: fixing one of two identical surfaces is
  exactly the "silently fix one" failure the spec warns against.*

- **Caller-safety decisions.** (A) `remint_reconcile_apply` now passes `strip_bom=strip_bom`
  into its plan call so apply and dry-run preview the SAME strip-intent metadata
  (classification unchanged either way). (B) `_retire_reconcile_content_anchor_class`
  keeps the default `strip_bom=False` so the shared content-identity anchor classifies on
  actual on-disk bytes and carries no strip-intent metadata into the anchor verdict.

## Packaging

- Version bump to `0.3.172` in `wom-kit/pyproject.toml`, `wom-kit/src/wom_kit/__init__.py`,
  and the root source-checkout shim `wom_kit/__init__.py` (bumped in lockstep so
  `test_bootstrap.test_root_wom_kit_shim_resolves_package` passes — a fourth version file
  beyond the spec's three), plus the capability-matrix header.
- CHANGELOG, release note `docs/releases/v0.3.172.md`, README + README.ko (current + prev
  baseline + one thematic bullet each), UPGRADE + UPGRADE.ko (additive flags + additive
  receipt field, no migration), and doc honesty updates to
  `object-storage-adapter-execution-contract.md` and `mint-receipt-reconcile.md`.

## Definition of done

Full `pytest`, `check_public_privacy`, and `check_release_readiness` all green, working
tree only, no real archive or basoon path touched, no real socket in any test.
