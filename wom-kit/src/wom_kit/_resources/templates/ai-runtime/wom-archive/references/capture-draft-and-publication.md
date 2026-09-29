# Capture, Draft, And Publication

Use this reference for files, AI conversation logs, transcripts, OCR material, generated documents, drafts, minting, revisions, and retirement.

## Preserve Source Before Summarizing It

Run source intake before copying or interpreting material as an archive source:

```text
archive source-intake <archive-root> --dry-run --local-path <local-file> --format json
```

For 1-1,000 reviewed local files, put safe item ids and local paths in one private
`wom-kit/source-intake-batch-request/v0.1` request. Preserve those request bytes:

```text
archive source-intake-batch <archive-root> --manifest <archive-local-json> --dry-run --format json
archive source-intake-batch <archive-root> --manifest <same-json> --approve --expected-plan-sha256 <exact-plan-sha256> --reviewed-by <actor> --format json
```

Relative paths resolve from the archive root. Output and receipts omit paths and
bodies. This decision records every intake receipt and one capture request. Keep
the returned content-free execution SHA-256. If interrupted, keep the request
unchanged; do not locate ids by hand or request another native decision. Use:

```text
archive source-intake-batch <archive-root> --manifest <same-json> --resume --reviewed-by <same-actor> --format json
```

WOM discovers one unambiguous authenticated started claim, revalidates the same
archive and request, and resumes only it. Otherwise stop at the public blocker.

Capture is a separate second decision. Do not rebuild its manifest; pass the
intake execution SHA-256 so WOM derives and authenticates the request:

```text
archive objet-capture-batch <archive-root> --source-intake-execution-sha256 <intake-execution-sha256> --dry-run --format json
archive objet-capture-batch <archive-root> --source-intake-execution-sha256 <same-intake-execution-sha256> --expected-plan-sha256 <exact-capture-plan-sha256> --approve --reviewed-by <actor> --format json
```

It revalidates the intake claim, checkpoints, receipts, bytes and archive
identity. After an interruption keep the archive, read `operation-control
--action recovery-plan --dry-run`, then continue with `--approve --resume
--approval-id <id> --execution-sha256 <sha>`; only `outcome_unverified` needs a
fresh dry-run and new approval. Neither decision authorizes providers, uploads,
links, drafts, minting, or cleanup.

Staged external originals also prepare one private name intake per copy
(`prepared_name_intake_count`). After capture, write them under one approval,
re-index, and `find-objet` finds the objet by its original filename (Windows only):

```text
archive objet-source-metadata-write <archive-root> --intake-batch <intake-execution-sha256> --dry-run --format json
```

AI conversation JSONL and AI-generated working documents may be preserved as
objets when they are relevant evidence; keep the original objet and a
human-readable zet as separate immutable layers. An explicit personal
`private_self` verbatim request overrides that default: preserve the selected
source in full (names, contacts, chronology, whitespace, wording) and let the
source-fidelity verifier bind the exact region. Credential secrets stay excluded
(human-controlled secret store). For client or public use keep the private source
unchanged and create a reviewed `sanitized_derivative`; its label is not access control.

Keep source text, OCR output, diagnostics and human corrections distinguishable; working metadata never silently becomes canonical prose.

Before drafting, revising, or linking records, preserve the artifact's time and
provenance. A matching name or label is not permission to reuse an identity,
merge two records, or erase a contradiction. A canonical zet is the current
human-reviewed state, not a truth certificate; change it through the reviewed revision path.

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
archive create-draft <archive-root> --dry-run --source-intake-plan <source-intake-plan.json> --prompt-boundary-report <prompt-boundary-report.json> --expected-archive-id <id> --expected-type <type> --profile-id <profile-id> --creation-mode ai_assisted --created-by ai_runtime:codex --assisted-by ai_runtime:codex --abstract <reviewed-abstract> --facet <key>=<value> --source-fidelity <verbatim|faithful_summary|sanitized_derivative> --fidelity-source-object-id <manifested-objet-id> --format json
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

An unminted draft is a working document: revise it with `draft-revision-write`
(a reviewed replacement proposal, `--dry-run` then `--approve`), including when
its title changes. Never edit the file by hand, and do not delete and recreate it. If the human reviews and decides
that it should not survive, use `discard-draft --dry-run`, then its exact
plan-hash-bound `--approve --reviewed-by` replay. Restore only through the
receipt-bound `discard-draft-restore` workflow. These commands never apply to
a minted/canonical zet.

To add a preserved objet to the draft's structured `assets`, use
`zettel-objet-link --dry-run` and its fresh plan-digest-bound, native
exact-human-approved replay (since v0.4.1). The objet must already be in the
manifest with a full 64-hex SHA-256 id. Since v0.4.40 `zettel-objet-link-revert
--approve` restores the exact prior bytes under the same exact approval; preview
it with `--dry-run` first and report only what its result states.

## Mint Only A Complete Reviewed zet

Before publication, require:

- an explicit, bounded, human-reviewed `frontmatter.abstract`;
- stable title, type, provenance, and source links;
- a `zet-quality-check --path <draft> --dry-run` with its blocker issues resolved;
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
