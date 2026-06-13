# Derived Text Capture

Status: implemented local CLI, first slice
Date: 2026-06-13

Derived text is text produced from a source objet:

```text
source object -> parser/OCR/ASR/vision text -> derived text record
```

The source object remains the evidence object. The derived text record is a
regenerable layer that records how the text was produced.

## Command

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

## What It Writes

Approved capture writes:

```text
objects/derived-text/sha256/<2>/<text-sha256>.txt
objects/manifests/derived-text.jsonl
receipts/derived-text-capture/<timestamp-random>.json
```

It does not modify the original object, create drafts, mint zets, call provider
APIs, run OCR, run ASR, run parsers, or run LLM vision.

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
