# Object Manifest Spec v0.1

Original files are represented as content-addressed objets. The technical identifier remains `object_id`.

The zettel layer should reference originals by `object_id`. Actual storage locations belong in the object manifest or SQLite metadata tables.

## JSONL Format

`objects/manifests/files.jsonl` is newline-delimited JSON. Each non-empty line is one object record.

## Required Fields

```json
{
  "object_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "logical_key": "objects/aa/aa/example.pdf",
  "mime": "application/pdf",
  "size_bytes": 12345,
  "locations": [],
  "provenance": {}
}
```

## Location Records

```json
{
  "provider": "local",
  "path": "objects/aa/aa/example.pdf",
  "availability": "available"
}
```

Provider examples:

```text
local
external_ssd
backblaze_b2
cloudflare_r2
aws_s3
google_drive_export
```

## Document Objets

Objet storage is not limited to media files.

Document files can also be represented as content-addressed source objets:

```text
.hwp
.hwpx
.docx
.xlsx
.pdf
.txt
.md
.csv
.pptx
```

If a `.md` file is a minted zettel, it belongs in the zettel layer.

If a `.md` or `.txt` file is an imported original source, it belongs in the source/objet layer and should be referenced by `object_id`.

The recommended default is:

```text
original source files -> local objet store and/or object storage provider
object identity -> object manifest
derived text -> derived text records with provenance
zets and metadata -> Git repository
search text -> SQLite/search index
```

## Derived Text Boundary

Text derived from an objet should not be confused with the objet itself.

Examples:

```text
OCR text from screenshot
OCR text from scanned PDF
speech-to-text transcript from audio
parser-extracted text from DOCX/HWPX/PDF
AI transcription of handwriting
human-reviewed correction of OCR
```

These should reference the source `object_id` and record derivation metadata:

```yaml
source_object_id: sha256:...
derivation_kind: ocr
tool_name: example-ocr-tool
tool_version: 1.0.0
confidence: 0.91
review_status: unreviewed
```

Born-digital text has higher authority than OCR-derived text. OCR and AI transcription should be treated as model-dependent derived records that can be regenerated later.

The first implemented CLI surface is:

```text
archive derive-text capture
```

It registers already extracted UTF-8 text. It does not run OCR, ASR, parser
extraction, LLM vision, provider APIs, drafting, or minting.

Approved capture stores:

```text
objects/derived-text/sha256/<2>/<text-sha256>.txt
objects/manifests/derived-text.jsonl
receipts/derived-text-capture/*.json
```

The first implemented `derivation_kind` vocabulary is:

```text
parser
ocr
asr
llm_vision
```

The first implemented `review_status` vocabulary is:

```text
unreviewed
human_corrected
```

## Portability Rule

The same objet may have many physical locations but one logical identity.

```text
logical duplication = bad
physical replication = good
```

## Zettel Boundary

Zettels may say:

```yaml
object_id: sha256:...
```

Zettels must not say:

```yaml
url: s3://...
url: b2://...
url: https://storage-provider.example/...
```

## Source Intake Boundary

`archive source-intake --dry-run` can resolve a supplied `object_id` or `objet:sha256:...` only when it already exists in `objects/manifests/files.jsonl`.

If the objet is missing from the manifest, source intake blocks instead of inventing a fake `object_id`. For local files and provider refs that are not manifested yet, it returns candidate/provider refs and next safe actions only.
