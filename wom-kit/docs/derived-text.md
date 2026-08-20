# Derived Text Capture

Status: implemented local CLI; paired multi-item batch recovery corrected in v0.3.315
Date: 2026-08-11

Derived text is text produced from a source objet:

```text
source object -> parser/OCR/ASR/vision text -> derived text record
```

The source object remains the evidence object. The derived text record is a
regenerable layer that records how the text was produced.

## Single-File Command

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli derive-text capture <archive-root> `
  --text-file <utf8-text-file> `
  --source-object-id sha256:<64-hex> `
  --derivation-kind parser `
  --tool-name <tool> `
  --tool-version <version> `
  --review-status unreviewed `
  --dry-run `
  --format json
```

In v0.4.0 stop after the dry-run. Single-item approval is fixed closed before
private text, source-object, manifest, or target reads with
`compound_exact_human_approval_binding_required` and writes nothing.

Before claiming extraction is complete, run the read-only coverage gate:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli derive-text coverage <archive-root> `
  --dry-run `
  --format json
```

See [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md).

Before choosing extraction tools, run the read-only local readiness doctor:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli derive-text doctor <archive-root> `
  --dry-run `
  --format json
```

If an extractor is installed outside `PATH`, pass a local hint file:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli derive-text doctor <archive-root> `
  --tool-hints local-tool-hints.json `
  --dry-run `
  --format json
```

The hint file can name executable paths for `soffice`, `libreoffice`,
`tesseract`, or `hwp5txt`. The doctor checks existence only and does not echo
the hint file path or executable paths.

## Batch Manifest Command

For hundreds or thousands of already extracted text files, use a JSONL manifest:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli derive-text capture <archive-root> `
  --from-manifest derived-text-ledger.jsonl `
  --dry-run `
  --format json
```

In v0.4.0 stop after the batch dry-run. `--from-manifest` approval has the same
fixed-close boundary and writes nothing.

Each non-empty JSONL line is one capture item:

```json
{"source_object_id":"sha256:<64-hex>","text_file":"derived/example.txt","derivation_kind":"parser","tool_name":"python-docx","tool_version":"1.0.0","review_status":"unreviewed","language":"ko","born_digital":true}
```

The JSON shape is also documented as a schema:

```text
wom-kit/schemas/derived-text-capture-manifest-item.schema.json
```

Required fields:

- `source_object_id`
- `text_file`
- `derivation_kind`
- `tool_name`
- `tool_version`
- `review_status`

Optional fields:

- `item_id`
- `model_name`
- `model_version`
- `confidence`
- `language`
- `born_digital`

For beginner operators, `tool_version` means the extractor version, parser
version, OCR engine version, ASR model version, or local script version that
created the text. If the extractor is a one-off local script, record a reviewed
script label such as `2026-06-16-local-script-v1` instead of leaving the field
blank.

Relative `text_file` paths are resolved from the JSONL manifest location. The
archive manifest and derived-text records do not store the local source text
file path.

Batch dry-run output is itemized. The top-level `items[]` array includes one
entry per non-empty JSONL line with `manifest_line`, `item_id`, `ok`,
`item_status`, `planned_action`, `blockers`, and `warnings`.

Read `item_status` as:

- `ready`: the item is structurally valid for review; it grants no v0.4 write
  authority.
- `skipped`: the item is already represented by the current batch or archive.
- `blocked`: the item cannot proceed; inspect that item's `blockers`.

The top-level `summary` counts the same item states, and top-level `blockers`
deduplicates all item blockers so automation can fail the whole batch safely.

## Historical Write Layout

v0.3 approved capture used this layout. v0.4.0 creates none of these files:

```text
objects/derived-text/sha256/<2>/<text-sha256>.txt
objects/manifests/derived-text.jsonl
receipts/derived-text-capture/<timestamp-random>.json
```

The v0.4 dry-run does not modify the original object, create drafts, mint zets,
call provider APIs, run OCR, run ASR, run parsers, or run LLM vision. Approval
does not reuse the historical single or batch writer and creates no item-level
receipt.

## Paired Multi-Item Objet Capture (v0.3.315)

`objet-capture-batch` can carry an already reviewed original/derived pair in
each request item. In addition to the ordinary `item_id`, `staged_path`, and
`source_intake_receipt_path`, a paired row supplies:

- `derived_text_staged_path`;
- `derivation_kind`, `tool_name`, `tool_version`, and `review_status`;
- optional `model` or `model_name` (never both), `model_version`,
  `confidence` including explicit null, `language` including explicit null,
  and `born_digital`.

The request is a closed JSON shape. Duplicate JSON keys, unknown fields,
missing paired dependencies, and conflicting legacy/current model names block
the whole request before source bodies are opened. The batch adapter preserves
all reviewed pairing fields in the exact generated selection instead of
reducing the row to an original-only item.

```powershell
archive objet-capture-batch <archive-root> `
  --manifest <archive-relative-request.json> `
  --dry-run --format json
```

The plan binds both `request_sha256` and `selection_sha256`. In v0.4.0 every
approval request returns `compound_exact_human_approval_binding_required`
before reading private staged content or writing any object, manifest row,
item receipt, or batch receipt. Historical v0.3 apply/recovery evidence remains
readable but is not replay authority.

Read the original and derived completion partitions separately:

```text
original_requested = original_written + original_skipped + original_blocked
derived_requested  = derived_written  + derived_skipped  + derived_blocked
```

In dry-run, `derived_ready` takes the place of `derived_written`. Text-mode CLI
output is derived from the actual returned partitions, not plan-time
expectations. One attempt-specific batch receipt binds the request, selection,
plan, lower capture receipt, terminal status, partition counts, reviewer, and
`attempt_sha256`.

Publication observation is tri-state: `verified_exact`, `not_written`, or
`ambiguous`. Separately, result states include `partial`,
`evidence_incomplete`, and `recovery_required`, while
`batch_capture_outcome_unverified` is a blocker code rather than a state. If a
lower exception or receipt publication ambiguity follows
possible durable object, manifest, or receipt writes, WOM does not guess what
happened. It returns fixed `next_safe_actions` such as
`fresh_dry_run_then_replay`,
`inspect_selection_collision_then_fresh_dry_run`, or
`fresh_batch_dry_run_then_reconcile`, and never automatically replays.

### Audit an interrupted v0.3.314 pair

Keep the original reviewed request unchanged and run a fresh dry-run. Do not
approve or replay it in v0.4.0. Existing receipts may be audited to identify
the original source object IDs; any separately supported exact single-write
route requires its own operation-specific approval. Do not copy originals
again merely to obtain those IDs. `partial`, `evidence_incomplete`, and
`recovery_required` remain review states.

## Paired Transcript Intake (v0.3.159)

When a vendor tool exports an original plus its transcript side by side (for
example Samsung Voice Recorder's `.m4a` + UTF-16 `.txt`), one reviewed
selection manifest can preview both halves:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli objet-capture-selection <archive-root> `
  --staged-path staging/incoming/call-2026-07-01.m4a `
  --source-intake-receipt receipts/sources/<plan>.json `
  --derived-text-staged-path staging/incoming/call-2026-07-01.txt `
  --derivation-kind asr `
  --tool-name samsung-voice-recorder `
  --tool-version <version> `
  --review-status unreviewed `
  --dry-run --format json
```

The generated manifest item carries a `derived_text` sub-object inside the
hashed manifest: `staged_text_path` (archive-relative), `approved_text_sha256`
(over the RAW file bytes — the always-blocking approval commitment mirroring
`approved_object_id`; a swapped transcript blocks with
`approved_text_content_mismatch`), the four required metadata fields
(`derivation_kind`, `tool_name`, `tool_version`, `review_status`), and the
optional `model_name`/`model_version`/`confidence`/`language`/`born_digital`.
Paired manifests use `action: local_objet_capture_with_derived_text_approved`
and `schema: wom-kit/b4-selection/v0.3`; pre-0.3.159 kits refuse them with
`selection_action_invalid` (fail-closed) instead of dropping the derived half.

`objet-capture --selection <path> --dry-run` validates the paired shape. In
v0.4.0, approval for `objet-capture-selection`, `objet-capture`, and
`objet-capture-batch` stops with
`compound_exact_human_approval_binding_required` before private staged input
reads or mutation. It publishes neither half and creates no selection,
manifest row, object, derived text, or receipt. Historical paired receipts
remain audit evidence only.

`staged_text_path` confinement has full parity with `staged_path` (containment,
internal-prefix block, reserved device names, never-touch, per-component
symlink/junction checks, `duplicate_selection_target` when a file appears as
both an original and a transcript source).

Honest scope notes:

- Paired intake preserves an exact staged transcript for cleanup only when the
  source was already BOM-free UTF-8, so the raw staged SHA-256 equals the
  canonical derived-text SHA-256, and strict manifest, store, and direct
  terminal receipt evidence all agree. BOM or UTF-16 transcoding changes the
  bytes, so `staged-cleanup-check` reports that staged `.txt` as not preserved.
  Preserve those raw bytes as a separate ordinary objet. A deferred entry is
  kept in staging and blocks folder cleanup; deferment is not discard approval.
- The v0.3.158 capture-enablement gate covers the paired derived half only
  because the pair runs INSIDE objet-capture; standalone derive-text capture
  remains ungated by design (`gate_scope` unchanged).
- Standalone `--text-file` accepts arbitrary absolute local paths; the
  manifest-carried `staged_text_path` is stricter because it is a persisted
  approval record. This asymmetry is deliberate.

## Encoding (v0.3.159)

Derived-text capture decodes input with a deterministic BOM-only ladder — no
chardet, no guessing, strict decoding everywhere — on ALL paths (standalone
single-file, `--from-manifest` batch, paired):

| Input | Result |
|---|---|
| UTF-8 BOM (`EF BB BF`) | decoded `utf-8-sig`, BOM stripped |
| UTF-32 LE/BE BOM | blocked `text_file_bom_encoding_unsupported` (checked BEFORE UTF-16: the UTF-32-LE BOM prefix-collides with UTF-16-LE's) |
| UTF-16 LE/BE BOM | strict decode, label from the sniffed BOM |
| no BOM | strict UTF-8 (exactly the old acceptance; stored bytes == raw bytes) |

Failure modes: a BOM-marked file whose bytes do not strictly decode blocks
with `text_file_bom_encoding_undecodable` plus a `detected_bom` field; decoded
text containing U+0000 blocks with `text_file_contains_nul` (the file is
likely BOM-less UTF-16/UTF-32 — transcode it); BOM-less non-UTF-8 keeps the
legacy `text_file_not_utf8` blocker with a hint naming the auto-handled
encodings. Files larger than the 64 MiB `DERIVED_TEXT_MAX_SOURCE_BYTES` cap
block with `text_file_too_large` before any bytes are read.

The stored text is decode -> strip leading BOM -> encode UTF-8, and NOTHING
else: CRLF and all other line endings are preserved byte-for-byte (the
transcript is evidence). `text_sha256`, `text_logical_key`,
`derived_text_id`, `size_bytes`, and lossless verification are all computed
over the STORED normalized UTF-8 bytes; `source_text_encoding` and
`source_text_sha256` (raw input bytes) are recorded in the record's
`provenance` and in receipts so the exact input can be identified. A hash does
not reconstruct a file by itself. When transcoding changes the bytes,
`derive-text coverage` and Doctor require the matching raw-byte hash to exist as
a manifested objet before manifest-scoped source-byte coverage passes. They
report the gap but never recreate an original from normalized text. This check
does not prove that the manifested bytes are currently available at a local or
remote location; availability remains a separate object-storage/recovery check.

Dedupe collapse: two encodings of identical text collapse to one
`derived_text_id`. The second registration is `skip_already_present` and the
stored record keeps the FIRST registration's `source_text_encoding`; the
second run's receipt still records the second source's encoding and raw hash.

Identity note for upgraders: utf-8-sig files were accepted before v0.3.159
with the BOM stored in the bytes, so the same utf-8-sig input now yields a
different `text_sha256`/`derived_text_id` than before (see UPGRADE.md).

## Vocabulary

First implemented `derivation_kind` values:

- `parser`
- `ocr`
- `asr`
- `llm_vision`

First implemented `review_status` values:

- `unreviewed`
- `human_corrected`

The older planning vocabulary in provenance documents remains useful design
context, but the CLI starts with this smaller operational vocabulary because it
matches current field feedback.

## Search

`archive index` ingests `objects/manifests/derived-text.jsonl` and reads the
stored UTF-8 text body. `archive search` can then return results with:

```json
{"type": "derived_text"}
```

The generated SQLite index is disposable. Rebuild it after adding or changing
derived text records.

## Privacy Boundary

The manifest stores an archive-relative text body path and provenance metadata.
It does not store the local source text file path passed with `--text-file`.

The derived text body itself can contain private source content. Safe archive
templates ignore `objects/derived-text/sha256/` by default, while manifest and
receipt records remain durable archive records.

## Coverage And Toolchain

v0.3.36 includes read-only derived-text coverage, toolchain recommendation,
toolchain doctor, non-echoed local tool hints, and agent operating contract commands. They help agents
enforce the rule that textual objets should be covered by derived text by
default, but they do not run OCR/parsers/ASR/vision and do not write files.

See [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md).
