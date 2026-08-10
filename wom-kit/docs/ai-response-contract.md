# AI Response Contract

Status: v0.3.313 source-fidelity and private-verbatim reporting checkpoint

`archive ai-response-contract` gives AI operators a read-only contract for
answering a human after running WOM commands.

It is not a web dashboard. It is a compact conversation/status-board contract:
what outcome to report, what evidence to cite, what privacy and approval
boundaries to preserve, and what remaining work to show.

## Command

```powershell
archive ai-response-contract <archive-root> `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive response-contract <archive-root> --dry-run
archive operator-response-contract <archive-root> --dry-run
```

## Required Response Sections

- `operation_outcome`: classify the command result before saying the work is complete.
- `evidence_basis`: say whether the evidence came from command output, a receipt, a release, a tag, or caller-supplied input.
- `privacy_boundary`: do not echo secret-like values, private locators, account identifiers, local absolute paths, tokens, or secret values.
- `approval_boundary`: only claim writes, live fetches, uploads, or privileged execution after explicit approval and receipt evidence.
- `remaining_work`: surface blockers, warnings, incomplete coverage, and next safe action.
- `openable_archive_references`: only tell the human that an archive file exists
  when the answer includes an archive-relative reference they can actually
  open.
- `human_record_integrity`: keep tool execution traces out of ordinary zet
  prose, re-read the whole document after revisions, resolve stale
  contradictions, and revise unminted drafts in place.

The optional `conversation_status_board` section allows a compact status summary
inside the AI answer. A separate web UI is not required.

At session start, surface `ai-start-here.inbox_attention`; do not let an
unpublished draft disappear behind unrelated work. A human publication request
starts the mint preview workflow. A draft write is not publication, and the AI
must not claim completion until an approved `mint-zet` result has canonical and
receipt evidence. When preview or approval is blocked, report that boundary in
the same response rather than silently deferring it.

If an index-backed search, view, or mint preview returns
`archive_index_rebuild_required`, report zero authoritative protected results
and the explicit rebuild-plus-health-check action. Do not turn stale rows, raw
SQLite output, or a silent live body scan into a successful answer.

`mint-zet --progress` separates liveness from outcome: content-free progress is
stderr evidence, while stdout is the final result. A heartbeat is not approval,
publication, or receipt evidence. Report the last completed stage when a caller
interrupts, and keep the durable outcome unknown until the official result or
recovery evidence is available.

For operator feedback, distinguish body completeness from lifecycle metadata
and delivery. Report `operator-feedback-compose` plan/approval evidence and the
content-free `operator-feedback-body-check` binding state separately; do not
claim a body, external submission, or human receipt from a metadata row alone.

When the answer is for a human, follow the plain-language convention: translate
git/infrastructure/WOM-internal jargon into everyday language and keep the exact
term in parentheses or in the logs (see `wom-ai-runtime-skill-plugin-layer.md`
and the `ai-response-concept-guide --topic git_infra_terms` set). This is
guidance an operator AI applies while writing; the command validates nothing and
enforces nothing.

The same runtime surfaces carry the AI-Operator Discipline norms an operator AI
applies while acting — provenance fidelity (record the source the human actually
encountered, never silently substitute a "more authoritative" one), enumerating
available tools before declaring a task impossible, and carrying
already-established/approved state instead of re-asking. Like the plain-language
convention, these are guidance the AI applies; this contract validates nothing and
enforces nothing about them.

Source fidelity has three distinct classes. A credential secret never belongs
in a zet. Private personal source data may be preserved without masking when a
personal archive owner explicitly requests `private_self` `verbatim`; the AI
must not substitute a summary for that request. A client or public result is a
separate `sanitized_derivative` and requires human review plus a separate share
decision. `verbatim` alone can have mechanical region verification under the
`utf8_newlines_lf` basis (newline conversion only, not trimming, Unicode
normalization, or BOM removal). `faithful_summary` and
`sanitized_derivative` remain human-reviewed semantic claims, never
machine-proven fidelity. If the human reports repeatable information loss, the
AI must route it through the official operator-feedback lifecycle instead of
dismissing it as merely its own mistake.

For every new AI-assisted or AI-generated draft, report the dry-run body and
source-fidelity plan evidence separately from the approved draft write and its
private receipt. Declared AI provenance cannot be described as human-written.
Before claiming publication, report the mint-time source/body re-verification
and the approved current fidelity-plan digest. Human-written creation remains
compatible; an older AI draft's attributed legacy review is not retrospective
verbatim proof. Reviewer attribution remains explicit, but private source
authority and excerpts stay out of ordinary output. Audience is not an ACL or
evidence of sharing, export, transport, or provider execution.

Before composing a zet, run `archive authoring-conventions <archive-root>
--dry-run --format json`. An archive may declare its durable writing rules at
`zettel-kasten/authoring-conventions.yml` using the
`wom-kit/authoring-conventions/v0.1` schema. If it has not declared them, the
command returns conservative defaults and an explicit warning; the AI should
ask instead of inventing a house format.

The command also returns `publication_completion_contract`: AI drafts use the
official `create-draft` preview/replay route, carry explicit abstract and facet
metadata, revise same-title unminted drafts in place, and treat publication as
complete only after mint evidence exists.

Commands, pipeline stage names, plan hashes, receipt counts, and internal tool
status normally belong in receipts rather than a human-facing zet body. They
may appear when the operation itself is the historical subject. The mint gate
uses fixed warning codes for likely tool traces and internally contradictory
status language, but these are review warnings rather than semantic proof.

## Related Taxonomies

The command ties together:

- `operation-status-taxonomy`,
- `input-provenance-taxonomy`,
- `secret-signal-taxonomy`,
- `approval-handoff-audit`,
- `status-board`.

## Safety Boundary

The command:

- reads no archive body text,
- accepts no sample values,
- echoes no sample values,
- calls no providers,
- checks no network,
- echoes no zettel body text, source values, local absolute paths, tokens, or secret values,
- writes nothing.

## Still Future

- Adding command-specific `status_class`, `input_provenance_class`, and
  `secret_signal_class` fields to more JSON outputs.
- Auditing write commands so every human-facing summary cites the relevant
  approval and receipt evidence.
- Adding a reusable renderer for compact conversational status-board summaries.
