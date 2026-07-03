# Derived Text Capture

Status: implemented local CLI; paired transcript intake and BOM-aware encoding since v0.3.159
Date: 2026-07-03

Derived text is text produced from a source objet:

```text
source object -> parser/OCR/ASR/vision text -> derived text record
```

The source object remains the evidence object. The derived text record is a
regenerable layer that records how the text was produced.

## Single-File Command

```powershell
python wom-kit\cli\archive.py derive-text capture <archive-root> `
  --text-file <utf8-text-file> `
  --source-object-id sha256:<64-hex> `
  --derivation-kind parser `
  --tool-name <tool> `
  --tool-version <version> `
  --review-status unreviewed `
  --dry-run `
  --format json
```

Use `--approve --reviewed-by <actor>` only after reviewing the dry-run.

Before claiming extraction is complete, run the read-only coverage gate:

```powershell
python wom-kit\cli\archive.py derive-text coverage <archive-root> `
  --dry-run `
  --format json
```

See [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md).

Before choosing extraction tools, run the read-only local readiness doctor:

```powershell
python wom-kit\cli\archive.py derive-text doctor <archive-root> `
  --dry-run `
  --format json
```

If an extractor is installed outside `PATH`, pass a local hint file:

```powershell
python wom-kit\cli\archive.py derive-text doctor <archive-root> `
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
python wom-kit\cli\archive.py derive-text capture <archive-root> `
  --from-manifest derived-text-ledger.jsonl `
  --dry-run `
  --format json
```

Use `--approve --reviewed-by <actor>` only after reviewing the batch dry-run.

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

- `ready`: the item is valid and would write or repair local derived-text
  records if approved.
- `skipped`: the item is already represented by the current batch or archive.
- `blocked`: the item cannot proceed; inspect that item's `blockers`.

The top-level `summary` counts the same item states, and top-level `blockers`
deduplicates all item blockers so automation can fail the whole batch safely.

## What It Writes

Approved capture writes:

```text
objects/derived-text/sha256/<2>/<text-sha256>.txt
objects/manifests/derived-text.jsonl
receipts/derived-text-capture/<timestamp-random>.json
```

It does not modify the original object, create drafts, mint zets, call provider
APIs, run OCR, run ASR, run parsers, or run LLM vision.

Batch mode reuses the same write path for each item. Approved batch runs may
write item-level receipts under `receipts/derived-text-capture/`.

## Paired Transcript Intake (v0.3.159)

When a vendor tool exports an original plus its transcript side by side (for
example Samsung Voice Recorder's `.m4a` + UTF-16 `.txt`), ONE reviewed
selection manifest can approve both halves:

```powershell
python wom-kit\cli\archive.py objet-capture-selection <archive-root> `
  --staged-path staging/incoming/call-2026-07-01.m4a `
  --source-intake-receipt receipts/sources/<plan>.json `
  --derived-text-staged-path staging/incoming/call-2026-07-01.txt `
  --derivation-kind asr `
  --tool-name samsung-voice-recorder `
  --tool-version <version> `
  --review-status unreviewed `
  --approve --reviewed-by <actor> --format json
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

`objet-capture --selection <path> --dry-run|--approve` then processes both
halves in one run: phase 1 publishes the original and fsyncs its manifest
line; phase 2 registers the derived text bound to the minted `object_id`. A
blocked original never reads its transcript (`blocked_by_original`). If the
original lands but the derived half blocks, the item and run report the
additive `status_class: partial` with `ok: false`; re-running the SAME
selection repairs it (the original half skips, the derived half retries), or
finish with standalone `derive-text capture --source-object-id <minted id>`.
The objet receipt (schema v0.3) item carries the full `derived_text`
sub-result including the derived receipt path; the derived receipt (schema
v0.2) carries `paired_with: {selection_manifest_id, selection_manifest_sha256,
item_id}`.

`staged_text_path` confinement has full parity with `staged_path` (containment,
internal-prefix block, reserved device names, never-touch, per-component
symlink/junction checks, `duplicate_selection_target` when a file appears as
both an original and a transcript source).

Honest scope notes:

- Paired intake does NOT preserve raw transcript bytes: the stored text is
  transcoded UTF-8, so `staged-cleanup-check` will correctly report the staged
  `.txt` as `not_preserved` (preservation requires an `objects/sha256` copy
  hashing to the raw digest). When raw-byte preservation matters, use the
  deferred list or a separate objet capture of the `.txt` itself.
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
`provenance` and in receipts so the raw input stays reconstructible.

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
