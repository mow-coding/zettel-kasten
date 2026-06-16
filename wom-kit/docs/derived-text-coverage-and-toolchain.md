# Derived Text Coverage And Toolchain

Status: v0.3.83 read-only coverage, manifest quality, toolchain doctor hints, and agent contract
Date: 2026-06-17

This document defines the read-only layer that helps an AI agent act on the
derived-text philosophy instead of merely quoting it.

The rule is:

```text
derived-text should cover every textual or plausibly textual objet by default.
maximum textual coverage is the default. Narrowing scope is the exception.
```

## Commands

Coverage gate:

```bash
archive derive-text coverage <archive-root> --dry-run --format json
archive derive-text-coverage <archive-root> --dry-run --format json
```

Toolchain recommendation:

```bash
archive derive-text toolchain <archive-root> --extension .pdf --dry-run --format json
archive derive-text-toolchain <archive-root> --extension .hwp --dry-run --format json
```

Toolchain readiness doctor:

```bash
archive derive-text doctor <archive-root> --dry-run --format json
archive derive-text-doctor <archive-root> --dry-run --format json
archive derive-text-doctor <archive-root> --tool-hints local-tool-hints.json --dry-run --format json
```

Agent operating contract:

```bash
archive derive-text agent-contract <archive-root> --dry-run --format json
archive derive-text-agent-contract <archive-root> --dry-run --format json
```

All four command families are read-only.

## What Coverage Checks

`derive-text coverage` reads:

- `objects/manifests/files.jsonl`,
- `objects/manifests/derived-text.jsonl`.

It does not read source object bodies.

It classifies each manifest object by extension and MIME hint, then checks
whether textual candidates have at least one derived-text record whose
`source_object_id` matches the object id.

If an older or external manifest record has no useful extension/MIME signal but
already has a matching derived-text record, coverage treats that derived-text
record as a conservative textual signal. In output this appears as
`textual_signal: derived_text_record_present`. This prevents prehashed external
ledgers that were originally registered as `application/octet-stream` from
collapsing a real extraction pass into a misleading `0/0` coverage reading.

Status values:

- `covered`: textual candidate has derived text.
- `missing_derived_text`: textual candidate has no derived text.
- `needs_password_or_encrypted`: manifest metadata says the source needs a
  password or is encrypted.
- `not_textual_or_unknown`: no extension/MIME signal says this is text-bearing.

The command returns `ok: false` when `missing_derived_text_count` is not zero.
This makes it useful as a gate before an agent claims the extraction pass is
complete.

v0.3.83 also returns `manifest_quality`. This checks the existing
`objects/manifests/derived-text.jsonl` records for required provenance metadata:

```text
source_object_id
derivation_kind
tool_name
tool_version
review_status
```

`tool_version` must name the extractor/parser/OCR/ASR/model/script version that
created the derived text. Values such as `unknown`, `n/a`, `none`, `todo`, or a
blank value are treated as quality issues. This means a manifest can no longer
look complete merely because every textual object has a derived-text row; the
rows also need enough tool provenance for a future human or AI runtime to audit
how that text was produced.

`manifest_quality.status` is `needs_review` when any derived-text record is
missing or weakening required provenance. The coverage gate returns `ok: false`
and includes blocker `derived_text_manifest_quality_issues` until those records
are fixed or recaptured.

v0.3.59 also returns `completeness_signal`. This is deliberately
manifest-scoped: it can say whether manifested textual objets have derived text,
but it is not proof that a Notion workspace, mailbox, cloud drive, or local
folder was fully mirrored. A full external mirror needs a separate
human-reviewed source/export mirror receipt.

## What It Does Not Expose

Coverage output does not echo:

- source file body,
- object filename,
- local absolute path,
- provider URL,
- secret value.

It can include `object_id`, extension, MIME type, coarse size bucket, and
toolchain family so a human or agent can plan the next extraction pass without
seeing private filenames.

## Toolchain Recommendation

`derive-text toolchain` does not run any tool. It only recommends the first
route an agent should consider.

Initial recommendations:

| Family | Route |
|---|---|
| `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html` | UTF-8/parser extraction |
| `.docx` | `python-docx` |
| `.xlsx` | `openpyxl` |
| `.pptx` | `python-pptx` |
| `.doc`, `.xls`, `.ppt` | LibreOffice headless conversion, then parser/OCR |
| `.hwp`, `.hwpx` | pyhwp/hwp5txt, LibreOffice fallback, HWPX zip/XML fallback |
| `.pdf` | PyMuPDF triage; parser for born-digital text; OCR/vision for scanned or complex layout; password flag for encrypted PDFs |
| image files | OCR, then human review; vision for handwriting, tables, forms, or complex layout |
| audio files | ASR route, then human review |

Reference docs used for the recommendation baseline:

- [python-docx](https://python-docx.readthedocs.io/)
- [openpyxl](https://openpyxl.readthedocs.io/)
- [python-pptx](https://python-pptx.readthedocs.io/)
- [LibreOffice command-line parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
- [Tesseract OCR documentation](https://tesseract-ocr.github.io/)
- [PyMuPDF documentation](https://pymupdf.readthedocs.io/)
- [pyhwp converters](https://pyhwp.readthedocs.io/en/latest/converters.html)

## Toolchain Doctor

`derive-text doctor` checks local readiness for the routes recommended by
`derive-text toolchain`.

It checks boolean availability for:

- Python module probes: `docx`, `openpyxl`, `pptx`, and `fitz`.
- Executable probes: `soffice`, `libreoffice`, `tesseract`, and `hwp5txt`.
- Policy-dependent routes such as local ASR, which are reported as not
  configured unless a future adapter defines them.

The doctor output does not echo executable paths, import paths, usernames,
local absolute paths, source filenames, source bodies, provider URLs, or secret
values. It reports only tool names, probe labels, booleans, route families, and
missing readiness categories.

If a tool is installed but not visible on `PATH`, provide a local JSON hint file:

```json
{
  "schema": "wom-kit/derived-text-tool-hints/v0.1",
  "executables": {
    "soffice": "<local-soffice-path>",
    "tesseract": "<local-tesseract-path>"
  }
}
```

Accepted executable hint keys are `soffice`, `libreoffice`, `tesseract`, and
`hwp5txt`. The doctor checks only whether the hinted file exists.
It does not execute the hinted tool. It does not echo the hint file path or any
hinted executable path.

The doctor does not install tools, import source files, run parsers, run OCR,
run ASR, call vision models, call providers, write derived text, or write
receipts.

## Agent Operating Contract

`derive-text agent-contract` returns the machine-readable rule set that agents
should load before extraction work:

- derived text is expected for every textual or plausibly textual objet unless
  a blocker is recorded,
- maximum coverage is the default,
- stopping at only PDFs is not enough when office files, HWP/HWPX, slides,
  spreadsheets, images, audio, or other text-bearing formats remain,
- coverage facts come from manifests, not subjective confidence,
- blockers must be recorded honestly,
- weak OCR/parser output must not be invented into clean prose.

## Closed Actions

These commands do not:

- run OCR,
- run parsers,
- run ASR,
- call LLM vision,
- call providers,
- read source bytes,
- hash source bytes,
- write derived text,
- write receipts,
- draft zets,
- mint zets.

They are coverage, manifest-quality, and routing gates. Actual extracted UTF-8
text is still registered through [Derived Text Capture](derived-text.md).
