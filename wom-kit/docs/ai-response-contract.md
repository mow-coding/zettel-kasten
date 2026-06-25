# AI Response Contract

Status: v0.3.155 AI response contract checkpoint

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

The optional `conversation_status_board` section allows a compact status summary
inside the AI answer. A separate web UI is not required.

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
