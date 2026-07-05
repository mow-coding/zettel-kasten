# Mint-Receipt Reconcile

`archive remint-reconcile` honestly reconciles a canonical zet with its mint
receipt after the canonical file drifts on disk — a CRLF/BOM re-checkout under
`core.autocrlf`, or a human content edit — by re-issuing the receipt's recorded
sha256 values. It exists because a mint receipt records the sha256 of the
canonical zet at mint time; if the bytes later change, `doctor` and `retire-draft`
correctly report a sha mismatch, and there was previously no honest, audited way
to update that record.

## Governing doctrine (R0)

Reconcile NEVER masks corruption, and classification NEVER waives human review.

- Every `--approve` shows you the current on-disk canonical content and requires
  `--reviewed-by`. No computed drift class unlocks a human-skipped path.
- Classification only DECORATES your decision (it names which fields changed and
  which acknowledgment is required). It never replaces it.
- The default class is the stricter `content_change`. `format_drift` is granted
  only on positive, byte-level, re-derivable proof. Any doubt → `content_change`.
- Hard refusals run before any classification. A state that cannot be honestly
  reconciled is refused; it is never fixed.

### The trust limit (read this before you `--approve` a `content_change`)

A reconciled receipt is only as trustworthy as the reviewer who ran it. When you
approve a `content_change` with `--content-changed-ack`, reconcile recomputes
`target.sha256` to match the **current, edited** canonical bytes and writes that
into the mint receipt — so `doctor` goes GREEN on that receipt afterward. That
green is **not** independent proof that the content is unchanged or correct; it
records that a named human (`--reviewed-by`) looked at the on-disk content and
vouched for it. The `--content-changed-ack` gate lets a reviewer bless an
*arbitrary* content change. The integrity guarantee of a `content_change`
reconcile record is therefore bounded entirely by that reviewer's judgment — the
receipt attests "a human accepted these bytes on this date," not "these bytes are
byte-identical to what was minted." A `format_drift` reconcile carries the
stronger, machine-checkable claim (bytes differ only by newline/BOM); a
`content_change` reconcile does not. Treat the reviewer field as the actual
warrant.

## Command

```
archive remint-reconcile <archive-root> (--zettel-id <id> | --path <rel>)
        [--dry-run | --approve]
        [--reviewed-by <actor>]
        [--content-changed-ack]
        [--strip-bom]
        [--format text|json]
```

- `--dry-run` (the default) classifies and previews with zero writes.
- `--approve` re-issues the receipt after review; it requires `--reviewed-by`.
- `--content-changed-ack` is required to approve a `content_change`.
- `--strip-bom` (opt-in) removes a single leading UTF-8 BOM; see below.

This command family is CLI-only. There is no MCP surface for reconcile, by design.

## Drift classes

`format_drift` — the canonical differs from its recorded sha only by newline or
BOM normalization. Granted ONLY when BOTH hold:

1. **Body identity via a clean snapshot.** The current canonical body is
   byte-identical (after newline/BOM normalization) to the draft snapshot, and
   the snapshot itself is a clean anchor (its raw sha still matches the recorded
   sha). A missing, BOM'd, or otherwise-mutated snapshot is never a clean anchor.
2. **Content frontmatter identity.** The FULL content frontmatter mint would have
   written is re-derived from the clean snapshot (every draft key, with
   `source_refs` transformed exactly as mint does) and compared field-by-field
   against the current canonical. Only the mint-managed keys — `status`,
   `updated_at`, `mint{}`, `promotion{}` — are excluded (they are injected at
   mint, not content); `status` is separately required to equal `canonical`.
   Because the comparison is over every content field and not a hand-picked
   subset, an edit to ANY content-bearing field (title, id, kind, visibility,
   facets, provenance, edges, created_at, …) is detected — no content field is
   invisible to the classifier.

`content_change` — everything else, and the default. This includes any body
change, any content frontmatter change (for example a title correction, a
`kind`/`visibility`/`facets` edit, or an appended edge that lives only in the
canonical frontmatter, not the snapshot), and every case where the snapshot
cannot be trusted as a clean anchor.

## Hard refusals (before classification)

Reconcile refuses — no sha is recomputed, nothing is written — when:

- the mint receipt is missing or is not a valid JSON object;
- `receipt.action != "mint_zettel"`, or the receipt is a dry-run receipt;
- the canonical zet id does not match the receipt zettel id (the swap case);
- the canonical target is unparseable, or its status is not `canonical`;
- the canonical `mint.receipt_path` does not point back to this receipt;
- `receipt.target.path` does not resolve to this canonical file.

## What approval writes (both receipts)

1. **In-place mint-receipt update.** All original receipt fields are preserved;
   only the three sha256 values (`source`, `target`, `snapshot`) are recomputed
   from the current on-disk bytes. An append-only `reconcile.history` block is
   added, carrying the prior/new shas, the drift class, the reviewer, and a
   `normalized_content_digest` (the sha256 of the newline+BOM-normalized
   canonical bytes) so a later human or `doctor` can re-derive the class
   independently. The latest block is mirrored at the top of `reconcile` so
   `doctor` reads one shape.
2. **Separate immutable audit receipt** under `receipts/mint/reconciles/<id>.reconcile.json`
   (a monotonic numeric suffix is used for a second reconcile of the same id).

Both writes are atomic (temp file + `os.replace`). Reconcile never edits zet
content; it records the sha of the bytes as they are.

## How doctor and retire route to reconcile

- `archive doctor`: a mint-target byte drift that a prior reconcile can prove is
  newline/BOM-only (its `normalized_content_digest` matches the current
  normalized canonical) emits `mint_receipt_target_byte_drift_suspected_format`
  and points to `remint-reconcile`. An un-reconciled mismatch keeps the plain
  `mint_receipt_sha_mismatch` error plus a suggested `remint-reconcile --dry-run`
  command. Both are ERRORs — they fail `doctor` and `--strict`. A UTF-8 BOM on a
  canonical zet also raises a `zettel_has_bom` WARN naming the cause.
- `archive retire-draft`: when — and only when — retirement is blocked by the
  mint-target sha-mismatch blocker, the output lists a `remint-reconcile
  --dry-run` next-safe action. No retire gate is relaxed.

## BOM and newline tolerance

Frontmatter parsing and receipt/JSON reads tolerate a single leading UTF-8 BOM.
The sha256 functions still hash raw bytes, so BOM and newline drift stay visible
as a sha mismatch — the tolerance makes files parse, it does not hide drift. New
mints pin the canonical write to LF newlines to reduce future re-drift.

## Snapshot-drift-aware classification (v0.3.167 Item 1)

A draft snapshot drifts on disk for the same reason a canonical does — a CRLF/BOM
re-checkout under `core.autocrlf`. Earlier releases fell straight to
`content_change` whenever the snapshot's raw sha differed, even if the drift was
newline/BOM-only. v0.3.167 adds a middle anchor tier so a genuinely format-only
snapshot drift can still yield `format_drift` — WITHOUT ever letting a
content-tampered snapshot launder a real edit.

Three anchor tiers, in order:

1. **`clean_anchor` (Tier A).** The snapshot's raw sha still matches the recorded
   sha. Body identity and frontmatter identity are both derived from the snapshot,
   exactly as before.
2. **`normalized_content_match` (Tier B).** The snapshot's raw sha differs, but
   `format_drift` is still granted when ALL of the following hold: (a) the current
   canonical body is byte-identical to the snapshot body under the one
   normalized-equality definition (CRLF/CR→LF, strip one leading BOM, zero Unicode
   normalization, no space collapsing); (b) the snapshot's OWN raw-vs-normalized
   delta is provably newline/BOM-only (no lone-CR or other byte change); and (c)
   the frontmatter field-diff is empty. Because the drifted snapshot is only
   newline/BOM-anchored (not sha-anchored), that field-diff is the **union of two
   independent checks**, and BOTH must be empty:
   - a **full-field reconstruction** comparing every content frontmatter field of
     the current canonical against the snapshot (the same all-fields diff Tier A
     uses — `visibility`, `kind`, `facets`, `provenance`, `edges`, `created_at`,
     `source_refs`, …, not just `id`/`title`). This catches a canonical-only edit
     to any field, including the fields the mint receipt never records; and
   - a **cross-check against the mint receipt's recorded `zettel`** (`id`/`title`).
     This catches the residual case where the snapshot's own frontmatter was
     tampered to match a tampered canonical (so the full-field diff would reproduce
     itself and read empty) — the receipt is sha-independent of the snapshot, so the
     tamper still surfaces.
3. **`content_change_fallback` (Tier C).** Everything else, and the default.

> **A content-tampered snapshot NEVER anchors `format_drift`.** Once the raw-sha
> anchor is relaxed (Tier B), body identity uses a normalized compare against the
> snapshot, while frontmatter identity uses the union above: a full-field
> reconstruction over EVERY content field PLUS a cross-check of `id`/`title` against
> the mint receipt. A canonical edit to any content field — including
> `visibility`, `kind`, `facets`, `provenance`, `edges`, `created_at` — makes the
> union non-empty and falls to `content_change`, and a snapshot whose frontmatter is
> tampered to match a tampered canonical is caught by the receipt cross-check. No
> single-field subset is trusted; a real content change can never be softened.

The reconcile audit receipt records a `classification_basis`
(`clean_anchor` / `normalized_content_match` / `content_change_fallback`) so an
auditor can see WHY a `format_drift` was granted when the snapshot itself was
dirty. The `drift_class` enum is unchanged: `format_drift` or `content_change`.

## Retire-draft reconcile (sibling command)

`archive retire-draft-reconcile <archive-root> --zettel-id <id> [--dry-run |
--approve] [--reviewed-by <actor>] [--content-changed-ack] [--strip-bom]` is the
sibling for a **retire-draft** receipt, which binds four raw-byte refs
(`source` / `target` / `mint_receipt` / `snapshot`) rather than the mint receipt's
three-sha shape. It is a separate command (not a flag on `remint-reconcile`) so the
safety-critical mint classifier stays single-purpose.

Honesty model (identical to mint reconcile): it recomputes the four refs from
current on-disk bytes, shows the on-disk content, is approval-gated, and requires
`--content-changed-ack` when ANY ref is `content_change`. Per-ref classification:

- `target` / `snapshot` (text refs): inherit the Item 1 discipline. A ref is
  `format_drift` only when the shared mint-reconcile classifier proves the
  canonical and snapshot content-identical (body identity + the full-field
  frontmatter union: an all-fields reconstruction over every content field plus the
  `id`/`title` receipt cross-check) AND the structural newline/BOM delta guard holds
  on the ref's bytes. A raw sha mismatch alone is never proof of content-identity,
  and an edit to any content field — not just `id`/`title` — forces `content_change`.
- `mint_receipt` (pure JSON pointer ref): no format dimension — any sha mismatch is
  `content_change`.
- `source` (the inbox draft): normally removed at retirement, so a missing source
  is not a drift.

Discoverability: `archive doctor` now attaches a `suggested_command`
(`archive retire-draft-reconcile <archive-root> --zettel-id <id> --dry-run`) to the
`mint_retired_draft_sha_mismatch` finding (previously a bare error). A byte-drift
FORMAT variant softens only when a prior retire reconcile recorded a
`normalized_content_digest` for that ref that still matches — the same honesty
precondition as the mint route. Both stay ERRORs. Sibling audit receipts live under
`receipts/mint/retired-draft-reconciles/<id>.retire-draft-reconcile.json`, and the
retire receipt gains an append-only `reconcile` provenance block.

## `--strip-bom` (format_drift by definition)

`--strip-bom` is an opt-in boolean on both reconcile commands that removes exactly
the 3-byte leading UTF-8 BOM (`EF BB BF`) from the canonical file. Because the BOM
carries no text content, stripping it is `format_drift` **by definition** — it is
not a new drift class, and the enum stays `["format_drift", "content_change"]`.

Guarantees:

- **Never changes text content.** It removes exactly `original[3:]` and asserts a
  content-preserving invariant (`normalized(before) == normalized(after)`) before
  committing; on any violation it aborts and writes nothing.
- **Atomic.** The rewrite uses temp-file + fsync + `os.replace`; a crash leaves the
  original byte-identical.
- **No-op refusal.** On a file with no leading BOM, it reports "no leading BOM
  present; nothing stripped" and rewrites nothing.
- **Never bypasses the ack gate.** When the run's class is `content_change`,
  `--strip-bom` still requires `--content-changed-ack`; a BOM strip never launders a
  real content edit. When the class is `format_drift`, it proceeds under that class
  and needs no ack.

The re-issued `normalized_content_digest` is recomputed over the post-strip bytes
(equal to the pre-strip normalized digest by construction, since the normalizer
already strips a leading BOM), so `doctor`'s format-drift branch still matches.

### `--strip-bom` dry-run parity (v0.3.172)

`--strip-bom` on a **dry-run** now previews the same strip-intent metadata an `--approve`
run records, so an operator can see the outcome before approving. When a leading BOM is
present the preview reports `bom_stripped: true` and `bom_strip_note: "would strip one
leading UTF-8 BOM from canonical"`; with no BOM it reports `bom_stripped: false` and
`"no leading BOM present; nothing stripped"` — a documented no-op that never previews a
byte rewrite. When `--strip-bom` is not passed the preview fields are omitted.

This is a strict **classification no-op**. The classifier is already BOM-insensitive
(the canonical is read with `utf-8-sig`, and the body compare strips the BOM and folds
newlines under the one normalized-equality definition), so `drift_class` and the
content-change ack requirement are identical whether `--strip-bom` is passed or not, for
every file. The strip preview only decorates the returned metadata; it never touches the
Tier A/B/C comparison. A BOM plus a real content edit stays `content_change` (ack
required) in the dry-run exactly as it does at apply — the strip never launders a content
change. **`retire-draft-reconcile` has the same dry-run parity**: its `--strip-bom`
dry-run previews the strip-intent metadata for the target canonical, and its
per-ref classification is likewise untouched.

## Scope note: contract-preview vs run-outcome (adapter honesty)

Unrelated to reconcile but corrected in the same release: the object-storage upload
result has two distinct `live_execution_allowed_now` signals. The static
CONTRACT-preview field is a capability statement (what the adapter is allowed to do
in general) and stays as declared; the top-level RUN-outcome field reports what a
specific run actually did — `true` only on a real executed upload, `false` on a
preview or blocked run. They are different signals and are not interchangeable.

## Deferred

The `remint-reconcile-batch` tier is deferred (its receipt directory name is
reserved). Per-id human judgment on each `content_change` is the point of the
doctrine, so a bulk content-change acknowledgment is intentionally not shipped.
