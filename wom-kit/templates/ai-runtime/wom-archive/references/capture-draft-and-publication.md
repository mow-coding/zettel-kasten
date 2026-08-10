# Capture, Draft, And Publication

Use this reference for files, AI conversation logs, transcripts, OCR material,
generated documents, drafts, minting, revisions, and retirement.

## Preserve Source Before Summarizing It

Run source intake before copying or interpreting material as an archive source:

```text
archive source-intake <archive-root> --dry-run --local-path <local-file> --format json
```

For many reviewed local files, put safe item ids and local paths in a private
`wom-kit/source-intake-batch-request/v0.1` manifest, then use one plan and one
approval gate:

```text
archive source-intake-batch <archive-root> --manifest <archive-local-json> --dry-run --format json
archive source-intake-batch <archive-root> --manifest <archive-local-json> --approve --expected-plan-sha256 <sha256:...> --reviewed-by <actor> --format json
```

The manifest's relative paths resolve from the archive root. Output and durable
receipts omit those path values and file bodies. The batch creates the same
individual source-intake plan records used by later capture and explicitly
claims only bounded per-item replay convergence, not atomic all-or-nothing
execution.

Stage selected bytes inside the archive root, prepare one reviewed capture
selection, and preview capture before approval. A source-intake plan is not
permission to copy, capture, import, or upload anything.

AI conversation JSONL and AI-generated working documents may be preserved as
objets when they are relevant evidence. Normally keep the original objet and a
human-readable zet as separate immutable layers. This default is not
permission to override an explicit personal `private_self` verbatim request:
in that case preserve the selected source in full, including names, contact
details, chronology, whitespace, and wording, and let the source-fidelity
verifier bind the exact source region. Credential secrets remain excluded and
must move through a human-controlled secret store. For a client or public use,
keep the private source unchanged and create a separately reviewed
`sanitized_derivative`; its audience label is not access control or permission
to share.

Keep source text, OCR output, parser diagnostics, confidence, and human
corrections distinguishable. Working metadata must not silently become
canonical prose.

Before drafting, revising, or linking records, preserve the artifact's time and
provenance. A matching name or label is not permission to reuse an identity,
merge two records, or erase a contradiction. A canonical zet is the current
human-reviewed archive state, not an objective-truth certificate. Use the
reviewed revision path when the current state changes so earlier evidence and
the chronology remain auditable.

## Create A Draft Through The Command Surface

First load this archive's human writing rules:

```text
archive authoring-conventions <archive-root> --dry-run --format json
```

When `state` is `declared`, follow those rules. When it is `undeclared`, use the
returned conservative defaults and ask the human before inventing a durable
format. Write for the future human reader. Do not put commands, pipeline stage
names, plan hashes, receipt counts, or tool verification statuses in the zet
body unless those operations are themselves the subject being documented.
After each edit, re-read the whole draft, remove stale contradictions, and
mention only archive files that the human can open from a real archive-relative
reference.

Use the validated source and prompt-boundary reports:

```text
archive create-draft <archive-root> --dry-run --source-intake-plan <source-intake-plan.json> --prompt-boundary-report <prompt-boundary-report.json> --expected-archive-id <id> --expected-type <type> --profile-id <profile-id> --creation-mode ai_assisted --created-by ai_runtime:codex --assisted-by ai_runtime:codex --format json
```

An AI-assisted or AI-generated draft must also supply a reviewed `--abstract`
and at least one stable `--facet key=value`. The command blocks before writing
when either is absent. It performs a bounded frontmatter-only same-title check;
an AI route cannot create a second unminted draft with the same normalized
title. Re-open and revise the existing draft instead.

Every new AI draft must declare exactly one source-fidelity mode:

- `verbatim`: the tool appends and verifies the complete selected source region;
- `faithful_summary`: a human approves a fixed candidate, while semantic
  fidelity remains unverified by the machine; or
- `sanitized_derivative`: a new reviewed derivative is created without
  changing or sharing the private source.

Use a manifested local content-addressed objet as the source authority. The
`utf8_newlines_lf` comparison changes only CRLF or lone CR to LF; it does not
trim, normalize Unicode, or remove a BOM, and it is explicitly not byte-exact.
Preview first, review the returned content-free plan digest, then replay with
`--approve`, the expected body and fidelity plan hashes, and `--draft-approved-by`.
Source text and paths do not belong in stdout, receipts, or error messages.

Do not manually copy local paths or unsafe source excerpts into frontmatter.
Never write Markdown directly into `inbox/`; a location policy is not a write
route. Draft approval writes only to `inbox/` through `archive create-draft`;
it does not approve minting.

An unminted draft is a working document: revise it in place, including when its
title changes. Do not delete and recreate it. If the human reviews and decides
that it should not survive, use `discard-draft --dry-run`, then its exact
plan-hash-bound `--approve --reviewed-by` replay. Restore only through the
receipt-bound `discard-draft-restore` workflow. These commands never apply to
a minted/canonical zet.

To add a preserved objet to the draft's structured `assets`, use
`zettel-objet-link --dry-run` and its exact approved replay. The objet must
already exist in the manifest and the object id must contain all 64 SHA-256
hexadecimal characters. Use `zettel-objet-link-revert` for exact-byte recovery;
it refuses to overwrite unrelated later edits.

## Mint Only A Complete Reviewed zet

Before publication, require:

- an explicit, bounded, human-reviewed `frontmatter.abstract`;
- stable title, type, provenance, and source links;
- a clean mint preview bound to the exact draft bytes;
- separate human approval for the mint write.

For an AI draft, also require a current source-fidelity plan. Mint re-reads the
manifested source and raw draft region, blocks any changed verbatim region, and
binds the reviewed current plan into the mint receipt. Only `verbatim` may be
reported as mechanically verified. `faithful_summary` and
`sanitized_derivative` remain human-reviewed claims even when every digest
matches.

`gist`, `summary`, `description`, and `overview` do not substitute for the
required abstract. A structural gate does not prove that the content is true,
complete, current, or suitable for an external audience.

Use the dedicated revision workflow for an already minted zet. Use retirement
only when the archive's lifecycle policy calls for it; never delete a canonical
zet or its receipts as cleanup.

When the human asks to publish, begin the `mint-zet --dry-run --progress`
workflow in that same task. A draft write is not publication. Do not claim
completion until the approved mint has produced both canonical and receipt
evidence. Progress goes to stderr and is not the final approval result. If the
preview reports `archive_index_rebuild_required`, explicitly rebuild and check
the index before replaying the unchanged publication request; never substitute
a silent live-body scan. If the preview finds another blocker or a separate
approval is still required, report that boundary immediately; never leave the
request silently pending for a later session.

## Keep Derived Work Synchronized

When a zet feeds a report, website, export, or other artifact, record the
dependency and audience. After either side changes, check whether the other is
stale. Internal notes, AI mistakes, secrets, and private operational detail
must not flow into public output merely because they exist in a source zet.

For the exact selection, capture, draft, mint, revision, and retirement command
flags, search [operator-contract.md](operator-contract.md) and the command's
bundled documentation before writing.
