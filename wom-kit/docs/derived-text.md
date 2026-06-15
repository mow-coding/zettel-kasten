# Derived Text Capture

Status: implemented local CLI, first slice
Date: 2026-06-13

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

v0.3.35 includes read-only derived-text coverage, toolchain recommendation,
toolchain doctor, and agent operating contract commands. They help agents
enforce the rule that textual objets should be covered by derived text by
default, but they do not run OCR/parsers/ASR/vision and do not write files.

See [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md).
