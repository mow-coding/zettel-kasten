# Text Provenance Hierarchy

Status: planning baseline with encountered-source fidelity (source-substitution axis)
Date: 2026-07-04

This document clarifies an important rule:

```text
not every text file has the same authority
```

`zettel-kasten` stores original text documents and AI/OCR-derived text, but it must not treat them as the same kind of evidence.

## 1. Core Principle

`zet` is always text.

But not every text artifact is a `zet`.

Text can appear in several layers:

```text
original editable document text
extracted parser text
OCR text
speech-to-text transcript
AI-generated transcript
human-reviewed transcript
minted zet
```

These layers should be preserved separately.

## 2. Suggested Authority Ladder

### L0: Original Source Object

The original file or capture.

Examples:

- `.hwp`
- `.hwpx`
- `.docx`
- `.xlsx`
- `.pdf`
- screenshot image
- scanned image
- audio recording
- video recording
- original `.txt` or `.md` source file
- provider page snapshot JSON such as Notion `recordMap` / `blocks`

This is the object that should receive an `object_id`.

It should not be overwritten just because a better parser, OCR model, or AI model appears later.

### L1: Born-Digital Text

Text that was actually authored or stored as editable text inside the source format.

Examples:

- text inside `.txt`,
- text inside `.md`,
- text inside `.docx`,
- text inside `.hwp` / `.hwpx`,
- text layer inside a digitally generated PDF.
- authored block text stored inside a provider page snapshot.

This has higher authority than OCR because the text was already present as text.

### L2: Deterministic Extraction Text

Text extracted from a born-digital document by a parser or converter.

Examples:

- extracting text from `.docx`,
- extracting text from `.hwpx`,
- extracting embedded PDF text,
- reading cells from `.xlsx`.
- extracting readable block text from a Notion page snapshot JSON.

This is still derived, so the extraction tool and version should be recorded.

### L3: OCR / ASR / AI Transcription Text

Text inferred from non-text signals.

Examples:

- OCR from screenshot,
- OCR from scanned PDF,
- speech-to-text from audio,
- subtitle/transcript from video,
- AI transcription of handwriting.

This layer is model-dependent and may improve over time.

It should always record:

- source object id,
- derivation kind,
- tool/model name,
- tool/model version when available,
- confidence when available,
- creation time,
- review status.

### L4: Human-Reviewed Derived Text

OCR, ASR, or AI transcription that a human reviewed and corrected.

This is stronger than raw OCR/AI output, but it is still a derivative of the source object.

The system should preserve:

```text
original object
raw OCR/transcript
human-reviewed transcript
review receipt
```

### L5: Minted zet

A human-approved text document that interprets, summarizes, connects, or records conclusions from source material.

This is archive memory, not raw evidence.

The minted zet should cite source objects and derived text records, but it should not replace them.

## 3. Practical Rule

For document and capture sources:

```text
original file/capture -> object layer
provider page snapshot JSON -> object layer
born-digital or extracted text -> derived text layer
OCR/AI transcript -> derived text layer with weaker authority
human-reviewed transcript -> reviewed derived text layer
minted zet -> zettel layer
```

For provider exports, keep the page snapshot and the readable text separate:

```text
Notion recordMap/blocks JSON -> source/original objet
extracted block text -> derived text record
human summary/decision -> minted zet
```

The raw JSON snapshot preserves provider structure and evidence. It is not a
human-readable zet just because it contains text fields.

## 4. Why This Matters

OCR and AI transcription quality changes over time.

If the archive treats OCR as the same as original text, future models cannot safely improve the record because the system will not know what was original and what was inferred.

Therefore:

```text
OCR output is useful,
but it is not the same as original editable text.
```

## 5. Recommended Metadata

Derived text records should eventually include:

```yaml
derived_text:
  derived_text_id: derived_text:example
  source_object_id: sha256:...
  derivation_kind: ocr
  tool_name: example-ocr-tool
  tool_version: 1.0.0
  model_name: example-model
  model_version: 2026-05-23
  confidence: 0.91
  language: ko
  review_status: unreviewed
  created_at: 2026-05-23T00:00:00Z
```

The first implemented CLI vocabulary for `archive derive-text capture` is:

- `parser`,
- `ocr`,
- `asr`,
- `llm_vision`.

Future `derivation_kind` values may include:

- `born_digital_text`,
- `parser_extraction`,
- `speech_to_text`,
- `video_transcript`,
- `ai_transcription`,
- `human_transcription`,
- `human_reviewed_correction`.

The first implemented CLI vocabulary for `review_status` is:

- `unreviewed`,
- `human_corrected`.

Future `review_status` values may include:

- `machine_only`,
- `human_spot_checked`,
- `human_reviewed`,
- `superseded`.

## 6. zet Boundary

A `zet` can quote or summarize OCR text.

But the `zet` should know whether it is based on:

- original editable text,
- parser-extracted text,
- OCR,
- AI transcription,
- human-reviewed correction.

That distinction belongs in provenance.

## 7. Encountered-Source Fidelity (Source-Substitution Axis)

Sections 1-6 answer one question: given the source object the human encountered,
which layer is a text artifact, and how much authority does it carry? The L0 rule
in section 2 is the **derivation-tool axis**: do not overwrite the source object
just because a better parser, OCR model, or AI model appears later.

There is a second, orthogonal axis: **which source object the human actually
encountered**. These are different concerns:

```text
derivation-tool axis   -> do not re-derive/overwrite the object with a "better tool"
source-substitution axis -> do not replace the encountered source with a "better source"
```

The rule for the source-substitution axis:

```text
record the source the human actually encountered,
not the "more authoritative" one behind it
```

If a person watched a Korean-subtitled edition of a video, read a specific
translation of a book, or saw one particular re-upload, THAT is the source object
of their thought. The archive should not silently "upgrade" it to the
original-language video, the first edition, or the canonical master — even when
that other source is objectively more authoritative. Substituting the source
corrupts the provenance of the user's actual encounter: the note now cites
something the user never saw.

Concretely:

- The encountered source (the exact video/edition/translation/language) is the L0
  object that receives the `object_id` and anchors the provenance.
- A "more authoritative" or "original" source is not a correction. If it is worth
  recording, add it as a SEPARATE reference (for example a related or `derived_from`
  source), never as a replacement of the encountered one.
- When a better source exists, the operator ASKS the human rather than swapping it
  in. The human may want both, or may care only about what they saw.

This complements the derivation-tool axis: one protects the object from being
re-derived by a newer tool; the other protects the object from being swapped for a
different, "more authoritative" source. Both preserve the same thing — the truth of
what the user's memory is actually based on. The behavioral norm for operator AIs
is stated as PROVENANCE FIDELITY in the AI-Operator Discipline section of the
runtime surfaces (the AGENTS.md templates, the runtime skill, and
`wom-ai-runtime-skill-plugin-layer.md`); it is guidance the AI applies, not a check
WOM enforces.

See also `notion-page-snapshot-model.md` for the provider page snapshot
boundary.
