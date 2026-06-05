# Source Objet Storage Policy

Status: active baseline
Date: 2026-05-25

This document answers a basic but important question:

```text
Where do files like hwp, hwpx, docx, xlsx, pdf, txt, and md live?
```

## 1. Core Rule

`zet` is always text.

But files that a `zet` refers to are source/original objets.

That means:

```text
zet
  -> v0.2 Markdown-compatible text + metadata envelope
  -> long-term WOM Safe HTML Profile canonical/interchange target

source/original objet
  -> hwp, hwpx, docx, xlsx, pdf, txt, md, images, audio, video, exports, and other files
```

The system should not confuse these two layers.

In WOM product language, the source/original item is an `objet`. The technical provider layer may still be called `object storage` because that is the standard API category used by S3-compatible services.

## 2. Objet Storage Is Not Only For Media

Objet storage is the archive warehouse for original files.

It is not limited to photos, videos, or audio.

Document files can also be stored as objets:

- `.hwp`
- `.hwpx`
- `.docx`
- `.xlsx`
- `.pdf`
- `.txt`
- `.md`
- `.csv`
- `.pptx`
- exported Notion files
- exported Google Drive files

The key question is not "is this media?"

The better question is:

```text
Is this an original source objet that a zet may cite, summarize, analyze, or derive from?
```

If yes, it belongs in the source/objet layer.

## 3. Recommended Default

Default policy:

```text
Original files -> local objet store and/or object storage provider
Object identity -> object manifest
Derived text -> derived text records with provenance
zets and metadata -> Git repository
Search text -> SQLite/search index
Human conclusions -> minted zets
```

For a first personal WOM setup, show the local folders explicitly:

```text
local archive root: C:\Users\<user>\zettel-kasten-<profile_slug>
local objet store:  C:\Users\<user>\zettel-kasten-<profile_slug>-objets
```

The local archive root is the Git-friendly control plane. The local objet store
is the raw source/original file store. Remote object storage such as R2, B2, or
S3 is a deferred manual external step unless the user explicitly chooses it.

In practical terms:

- Git should store zets, schemas, manifests, receipts, and small public-safe examples.
- Objet storage should store original binary or document files when they are real archive sources.
- Derived OCR/transcription/extraction text should be stored with provenance and review status.
- SQLite/search indexes may store extracted text for search, but indexes are rebuildable.
- zets should cite original objets through `object_id`, not by embedding the file itself.

## 4. File-Type Guidance

### HWP / HWPX

Treat as source/original document objets.

Recommended storage:

```text
object storage provider or local objet store
```

The system may later extract text for search or AI drafting, but the original `.hwp` or `.hwpx` remains the source objet.

### DOCX / XLSX / PPTX

Treat as source/original document objets.

Recommended storage:

```text
object storage provider or local objet store
```

These are structured documents, but Git diffs are usually not useful for them. Keep the original as an objet and store extracted text/metadata separately.

### PDF

Treat as a source/original objet.

Recommended storage:

```text
object storage provider or local objet store
```

The system may keep extracted text, OCR results, page references, or summaries as derived metadata or zets.

Digitally generated PDFs and scanned PDFs should be distinguished:

```text
digital PDF text layer -> parser extraction from born-digital text
scanned PDF image -> OCR-derived text
```

OCR-derived text has weaker authority than born-digital text unless it is reviewed.

### TXT / MD

There are two cases.

If the `.txt` or `.md` file is a minted `zet`, store it in Git under the zettel layer.

If the `.txt` or `.md` file is an imported original source, treat it as a source objet:

```text
source objet -> object manifest
derived conclusion -> minted zet
```

This distinction matters because a copied original note and a newly minted canonical zet have different provenance.

### CSV

Treat as a source/original objet unless it is a tiny public-safe example.

The system may also derive:

- schema metadata,
- column summaries,
- statistical notes,
- minted zets.

### Public Documentation

Project documentation, specs, README files, and open-source examples belong in Git because they are part of the public project itself.

They are not the user's private source archive.

## 5. Why Not Put Everything In Git?

Git is excellent for:

- text source code,
- specs,
- schemas,
- zets,
- receipts,
- manifests,
- public docs.

Git is less ideal for:

- large files,
- binary document formats,
- frequently changing office files,
- private raw source dumps,
- files that need separate access control.

So the archive should avoid using Git as the universal warehouse.

## 6. Why Keep Objet Manifests?

The object manifest lets the system say:

```text
This zet was derived from exactly this original objet.
```

without forcing the original file to live in the same Git repo.

The same objet may have several physical locations:

```text
local PC
external SSD
object storage provider
Google Drive export
Notion export
backup disk
```

but one logical identity:

```text
sha256:...
```

## 7. AI Drafting Flow

For document files, the typical flow is:

```text
register source file
-> hash and record object manifest entry
-> extract text or metadata when possible
-> create draft zet
-> human reviews
-> mint zet
-> canonical zet cites object_id
```

The original document remains an objet. The minted zet becomes durable archive memory.

## 8. v0.2.21 Setup Planner

WOM-kit v0.2.21 adds a dry-run-first setup planner for the technical object storage provider layer:

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:username \
  --profile-slug username \
  --storage-account-ref storage:account:username \
  --format json
```

The default bucket/container proposal is:

```text
zettel-kasten-<normalized-profile-slug>-objets
```

The default prefix proposal is:

```text
archives/<archive_id>/objets/
```

Dry-run writes nothing and calls no provider APIs. Approved mode writes only safe local provider metadata and a setup receipt. It still does not create buckets, run OAuth, upload, sync, copy source files, hash files, or import source content.

## 9. v0.2.22 Source Intake Planner

WOM-kit v0.2.22 adds a dry-run-only source intake planner:

```bash
archive source-intake <archive-root> --dry-run --object-id sha256:<hash> --format json
```

Use it before `create-draft --dry-run` when a draft is based on a presentation, document, image, provider item, local file, source map item, manifested objet, or AI artifact.

The planner returns safe `source_refs_for_draft`, `objet_status`, object storage context, and content access flags. It writes nothing and does not read file bodies, calculate full hashes, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts, or mint.

## 10. Text Provenance Hierarchy

The archive should preserve the difference between:

```text
original editable text
parser-extracted text
OCR/AI transcription text
human-reviewed derived text
minted zet
```

These are all text-like artifacts, but they do not have the same authority.

OCR and AI transcription can improve as models improve, so they must remain traceable to the original objet and tool/model that produced them.

See `text-provenance-hierarchy.md`.
