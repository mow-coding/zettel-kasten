# Capture, Draft, And Publication

Use this reference for files, AI conversation logs, transcripts, OCR material,
generated documents, drafts, minting, revisions, and retirement.

## Preserve Source Before Summarizing It

Run source intake before copying or interpreting material as an archive source:

```text
archive source-intake <archive-root> --dry-run --local-path <local-file> --format json
```

Stage selected bytes inside the archive root, prepare one reviewed capture
selection, and preview capture before approval. A source-intake plan is not
permission to copy, capture, import, or upload anything.

AI conversation JSONL and AI-generated working documents may be preserved as
objets when they are relevant evidence. Do not paste a raw conversation log
into a canonical zet. Create a human-readable zet that states the durable
decision or knowledge and links to the preserved source objet.

Keep source text, OCR output, parser diagnostics, confidence, and human
corrections distinguishable. Working metadata must not silently become
canonical prose.

## Create A Draft Through The Command Surface

Use the validated source and prompt-boundary reports:

```text
archive create-draft <archive-root> --dry-run --source-intake-plan <source-intake-plan.json> --prompt-boundary-report <prompt-boundary-report.json> --expected-archive-id <id> --expected-type <type> --profile-id <profile-id> --creation-mode ai_assisted --created-by ai_runtime:codex --assisted-by ai_runtime:codex --format json
```

Do not manually copy local paths or unsafe source excerpts into frontmatter.
Draft approval writes only to `inbox/`; it does not approve minting.

## Mint Only A Complete Reviewed zet

Before publication, require:

- an explicit, bounded, human-reviewed `frontmatter.abstract`;
- stable title, type, provenance, and source links;
- a clean mint preview bound to the exact draft bytes;
- separate human approval for the mint write.

`gist`, `summary`, `description`, and `overview` do not substitute for the
required abstract. A structural gate does not prove that the content is true,
complete, current, or suitable for an external audience.

Use the dedicated revision workflow for an already minted zet. Use retirement
only when the archive's lifecycle policy calls for it; never delete a canonical
zet or its receipts as cleanup.

## Keep Derived Work Synchronized

When a zet feeds a report, website, export, or other artifact, record the
dependency and audience. After either side changes, check whether the other is
stale. Internal notes, AI mistakes, secrets, and private operational detail
must not flow into public output merely because they exist in a source zet.

For the exact selection, capture, draft, mint, revision, and retirement command
flags, search [operator-contract.md](operator-contract.md) and the command's
bundled documentation before writing.
