# Safety, Results, And Human Language

Use this reference when interpreting a command result, choosing the next safe
action, or explaining WOM state to a person who should not have to decode the
internal machinery.

## Read The Result, Not The Activity

For every command, verify:

- process exit code;
- final structured result, not only progress lines;
- archive identity and resolved path policy;
- `dry_run`, approval, write, provider, and secret-access flags;
- bounded problem counts and truncation indicators;
- receipt path and digest after an approved write;
- whether rollback or cleanup completed after a failure.

No output is not success. Endless progress is not success. A result file that
cannot be parsed is not success. Preserve the diagnostic artifact when it is
safe, then report the last verified phase and the remaining uncertainty.

## Default Safe Actions

Safe defaults include:

- resolve the active profile;
- run prompt-boundary and source-intake previews;
- read abstract/catalog/freshness surfaces;
- run Doctor or a targeted read-only audit;
- inspect plans and exact expected changes;
- ask for human approval only after a bounded preview.

Unsafe shortcuts include:

- editing canonical files, receipts, locks, indexes, or profile state by hand;
- assuming an MCP check can approve a CLI write;
- treating a plan, candidate, receipt, or successful upload as a canonical mint;
- echoing secrets, credential responses, absolute private paths, or source
  bodies into logs or chat;
- scanning unrelated directories or development projects as archive material;
- retrying a noisy or hung command indefinitely without a bounded diagnosis.

For the exhaustive historical allow/deny list, read the `Safe Actions` and
`Boundaries` sections of [operator-contract.md](operator-contract.md).

## Explain State In Ordinary Language

Lead with the human meaning:

- "published note" before `canonical zet`;
- "source file" before `objet` when the exact term is unnecessary;
- "change record" before `receipt`;
- "health check" before `Doctor`;
- "preview" before `dry-run`;
- "approved after review" before a list of write flags.

Then give the exact command, field, or internal term in parentheses or a code
block when the person needs to verify or repeat the action.

Do not dump a status dashboard merely because data exists. Answer the current
question first, then show only the status lines that change the decision.

## Preserve A Durable Handoff

When a session produces a substantial decision, correction, implementation,
or unresolved risk:

1. preserve relevant raw evidence as an objet when appropriate;
2. write or revise the human-readable zet that carries the durable meaning;
3. link provenance and derived artifacts;
4. record what is complete, what needs human review, and what still requires
   real-use feedback.

The next AI should be able to recover the work from the archive without relying
on the vanished chat session.
