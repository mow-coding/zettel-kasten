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
        [--format text|json]
```

- `--dry-run` (the default) classifies and previews with zero writes.
- `--approve` re-issues the receipt after review; it requires `--reviewed-by`.
- `--content-changed-ack` is required to approve a `content_change`.

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

## Deferred

The `remint-reconcile-batch` tier is deferred (its receipt directory name is
reserved). Per-id human judgment on each `content_change` is the point of the
doctrine, so a bulk content-change acknowledgment is intentionally not shipped.
