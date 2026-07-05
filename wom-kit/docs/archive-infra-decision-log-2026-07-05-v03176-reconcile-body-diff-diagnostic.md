# Decision Log — v0.3.176 Content-Free Reconcile Body-Diff Diagnostic (DX-only)

Date: 2026-07-05
Batch: v0.3.176 (implements the LOCKED spec: "reconcile body-diff diagnostic, DX-only").
Anchor tree at spec authoring: HEAD `feb4ae9d` (v0.3.175), tree clean.
Release action: working tree only — no git commit/tag/push (main session releases after
gates). Never touches a real archive or `zettel-kasten-basoon`, and makes no network call.

This log records DEC-1..DEC-16 with one-line rationales and the Q1-Q6 safety resolutions, per
the AGENTS.md decision-log mandate.

## The problem this batch fixes

The basoon 5th operator letter (§4) reported a client running
`remint-reconcile --strip-bom --dry-run` on a zet (`source_outline`) and getting
`drift_class=content_change` + `body_changed:true` + ack required, with no obvious post-BOM
text edit visible.

The classifier is **correct** and must NOT change. `bytes_normalized_for_content_compare`
folds ONLY a single leading UTF-8 BOM and CRLF/CR→LF (the v0.3.167 locked "zero Unicode
normalization, no whitespace collapse" honesty). A residual AFTER that normalization is beyond
BOM (trailing whitespace, final-newline presence, NFC vs NFD, or a real content edit), so
`content_change` is the HONEST class. Folding more would launder a real edit to `format_drift`
— a cardinal sin. There is **no classifier change**. The fix is DX-only: surface a
CONTENT-FREE diagnostic so the client can self-diagnose WHICH residual they hit.

## Nature of change

This is a **STRICT CLASSIFICATION NO-OP** and **DX-ONLY** change.
`bytes_normalized_for_content_compare`, the Tier A/B anchor logic, the drift_class predicate,
`classification_basis`, and `content_change_ack_required` are byte-identical with and without
this change. We add a content-free, output-only diagnostic decoration; the classifier is
untouched.

## Decisions

- **DEC-1 — helper signature and location.** One pure module-level function
  `_reconcile_body_diff_diagnostic(canonical_body: str, snapshot_body: str) -> dict[str, Any]`
  co-located immediately after `bytes_match_after_normalization`. *Rationale:* a single pure
  helper next to the normalization primitives it reuses keeps the classifier scope untouched
  and makes the no-op property obvious by construction. It is never called with `None`
  (caller-guarded, DEC-9).
- **DEC-2 — reuse the locked primitive read-only.** The helper normalizes each side via
  `bytes_normalized_for_content_compare(body.encode("utf-8"))`, the SAME forms the classifier
  compared. *Rationale:* the reported offset/delta must explain the exact residual the
  classifier saw; reusing the identical primitive guarantees that. The primitive is not
  modified.
- **DEC-3 — statement of primitive identity.** The bytes fed to the diagnostic are the exact
  same call the drift_class body-identity proof uses; the diagnostic adds ZERO normalization of
  its own beyond category-transform probes computed on copies, and never mutates the
  offset/delta forms. *Rationale:* the diagnostic explains precisely the residual the
  classifier folded down to, no more, no less.
- **DEC-4 — fields (all content-free).** The dict has EXACTLY: `differs` (bool), `category`
  (str), `first_differing_byte_offset` (int), `normalized_length_delta` (int), `canonical_form`
  (str), `snapshot_form` (str). No field ever holds a body substring/slice/repr/sample.
  *Rationale:* ints + closed enums only; the fixed key set makes the not-a-substring test total.
- **DEC-5 — fixed category set.** `final_newline_only`, `trailing_whitespace_only`,
  `unicode_normalization_only`, `content_difference` (plus `none` on the sentinel). There is NO
  `whitespace_only` category. *Rationale:* both critiques required dropping/hard-constraining
  `whitespace_only` (internal/leading collapse launders a semantic edit under the v0.3.167 "no
  whitespace collapse" lock); `trailing_whitespace_only` already covers the honest per-line
  rstrip case. DROPPED entirely.
- **DEC-6 — defensive equal-after-normalization sentinel.** If `canonical_norm ==
  snapshot_norm`, return `differs:false`/`category:none`/offset `-1`/delta `0`/forms `n/a`.
  *Rationale:* unreachable when `body_changed True`, but guards any future skew; carries no
  offsets/text.
- **DEC-7 — offset semantics.** `first_differing_byte_offset` is the first differing byte
  index between the two `bytes` normalized forms, or `min_len` when one is a strict prefix of
  the other. A plain int, never a slice. *Rationale:* deterministic for the prefix/length
  mismatch case; a pure index reveals position but no bytes; matches the classifier's
  `.encode("utf-8")` byte domain.
- **DEC-8 — ordered category check with the FULL-RECONCILIATION honesty rule.** After the
  sentinel, try transforms in order (final newline → per-line trailing rstrip → NFC), and a
  non-`content_difference` category is reported ONLY when its transform makes the TWO normalized
  bodies EQUAL TO EACH OTHER (mutual, symmetric). First fully-reconciling transform wins; else
  `content_difference`. *Rationale:* the mutual-full-reconcile invariant is the core
  anti-laundering guarantee; ordering gives the most specific honest label; a mixed diff fails
  every transform's mutual-equality and correctly lands on `content_difference`.
- **DEC-9 — merge into `remint_reconcile_plan` (strict no-op placement).** Compute and merge
  AFTER the dict literal closes, mirroring the strip_bom_preview merge, guarded by
  `body_changed is True and snapshot_body is not None`. *Rationale:* exactly mirrors the proven
  strip_bom_preview no-op template; the key is added to an already-built dict, downstream of and
  invisible to classification. On Tier C (`body_changed` None) or `format_drift` (`body_changed`
  False) the key is ABSENT.
- **DEC-10 — NFC/NFD form labels.** Inside the `unicode_normalization_only` branch only, derive
  each side's form by comparison (`nfc`/`nfd`/`mixed`), never by emitting characters; `n/a`
  elsewhere. *Rationale:* closed enum computed by comparison; reported only when NFC fully
  reconciles with no other residual, so an NFD+content or NFD+whitespace mix is
  `content_difference`.
- **DEC-11 — retire parity via threaded sub-plan diagnostic.** Retire has no
  `canonical_body`/`snapshot_body` in scope; thread the inner remint plan's already-computed
  diagnostic up: `_retire_reconcile_content_anchor_class` now returns `{drift_class,
  body_diff_diagnostic}`; the plan call site unpacks the string for ref reports and captures the
  diagnostic; the retire `classified_result` merges it after the dict closes. The apply-path
  caller unpacks only the `drift_class` string. *Rationale:* the minimal change that reuses the
  exact same helper output — the retire plan carries the IDENTICAL dict the remint plan
  produced — with no body symbols introduced into retire scope and no apply-path behavior change.
- **DEC-12 — CLI text summary: remint printer.** One content-free line after the `body_changed`
  line, inside `if show_content:`, gated on the key being present and `differs`. Only numbers +
  fixed labels. *Rationale:* fires exactly when the operator needs to self-diagnose
  (content_change or --approve); strictly less information than the full canonical text already
  printed, but stays content-free for JSON consumers and hygiene.
- **DEC-13 — CLI text summary: retire printer.** The parallel line after the `ref_reports` loop,
  gated on the key. *Rationale:* parity with remint; content-free; only when present.
- **DEC-14 — tests T1–T23.** Category correctness, anti-laundering attacks, classification
  invariance, guards, content-free/privacy, primitive lock, retire parity, and offset semantics.
  *Rationale:* covers every required change and every attack from both critiques with a pinned
  test.
- **DEC-15 — packaging/parity.** Version bump three files to 0.3.176; CHANGELOG top; release
  note; this decision log; capability-matrix header + previous-checkpoint line; README/README.ko
  baseline + one paired EN/KO bullet; UPGRADE/UPGRADE.ko additive note. *Rationale:* matches the
  batch/maintenance contract exactly.
- **DEC-16 — gates.** `pytest tests/ -q`, `check_public_privacy`, `check_release_readiness`, all
  green, foreground. *Rationale:* the release contract; privacy check backstops the no-content-echo
  guarantee, readiness check backstops packaging parity.

## Safety questions — resolved

- **Q1 (no-op):** DEC-3, DEC-9 — added after the dict literal, mirroring strip_bom_preview; the
  predicate never reads it; pinned by the classification-baseline test (T12). SATISFIED.
- **Q2 (no content echo):** DEC-4/DEC-7/DEC-10 emit only ints + closed enums; pinned by
  T17/T18/T19. SATISFIED.
- **Q3 (mixed-diff honesty):** DEC-8 mutual full-reconcile invariant; `whitespace_only` DROPPED
  (DEC-5); pinned by T5–T11. SATISFIED.
- **Q4 (None/format_drift guards):** DEC-6 sentinel + DEC-9 `body_changed is True and
  snapshot_body is not None` guard; helper never called with `None`; pinned by T13–T16.
  SATISFIED.
- **Q5 (primitive locked):** DEC-2 read-only reuse; `bytes_normalized_for_content_compare`
  untouched; pinned by T20. SATISFIED.
- **Q6 (NFC/NFD accuracy):** DEC-8 step 3 requires NFC to fully reconcile; DEC-10 closed enum;
  pinned by T3/T10/T11. SATISFIED.
