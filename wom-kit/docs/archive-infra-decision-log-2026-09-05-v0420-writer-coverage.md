# Session integration covers real dispatch families

## Context

A parser option is not proof of an executable writer. Likewise, adding one
argument or changing the native broker cannot bind every existing local record.
The integration audit ran the actual parser and capability inventory at the
development checkpoint: 315 canonical paths, 47 approval-available paths (ten
conditional), 67 fixed-closed paths and 201 paths without exposed approval.
These are dispatch-surface facts, not successful client execution counts.

One of the 47, `operation-control`, has no mutation: cancel always returns an
unsupported result and the other actions require read-only mode. Its v0.4.19
capability correction is separate from v0.4.20 writer integration. It must not
be implemented or counted as a newly available session writer by accident.

## Explicit coverage groups

| Family | Paths at the audited checkpoint |
| --- | --- |
| Exact manifest (10) | `external-locator-record`, `git-backup-reconcile-plan`, `migrate`, `object-storage`, `object-storage-adopt-existing`, `objet-capture-selection`, `source-intake-batch`, `source-intake-record`, `zet-title-remap-revert`, `zet-title-remap-write` |
| Native/custom domain (15) | `approval-integrity-overlay`, `create-draft`, `credential-adopt`, `duplicate-object-reconcile`, `human-artifact-register-root`, `human-artifact-transition`, `mint-zet`, `objet-capture`, `objet-capture-batch`, `project-version-update`, `promote`, `retire-draft`, `revert-edge`, `source-fidelity-session-evidence`, `zettel-edge` |
| Mixed single/manifest (1) | `zettel-objet-link` |
| Existing local records and saved plans (20) | `activity-group-membership-removal-plan`, `ai-usage-record`, `approval-handoff-record`, `credential-access-approval-plan`, `imap-mailbox-adapter-audit-write`, `imap-mailbox-header-scan-receipt-audit`, `imap-mailbox-material-capture-approval-plan`, `imap-mailbox-material-selection-record`, `operational-context`, `operator-feedback-compose`, `operator-feedback-mark-delivered`, `operator-feedback-record`, `project-intake-decisions`, `project-intake-record-answer`, `project-intake-unpack-choice`, `record-attestation-review-candidate`, `record-attestation-statement-draft`, `relation-candidate-decide`, `session-handoff-checkpoint`, `shared-update-attestation-review` |
| Unsupported control (1) | `operation-control` |

The local-record group is not an exact-native approval implementation. For
example, feedback composition has its own CAS contract and legacy handoff uses
its v1 digest and receipt. IMAP entries here save local evidence or plans; they
do not open the unavailable IMAP provider writers.

## Decisions

1. Classify parsed execution intent before ownership enforcement: read-only,
   fresh write, existing resume, bootstrap, emergency preservation or unsupported
   control. `approve=True` alone does not identify a fresh operation.
2. For fresh domain writes, acquire the existing archive lock, validate current
   app/session/claim ownership, observe a fresh plan, and then request approval.
   Reuse that held lock in the writer; do not nest a second archive lock.
3. A historical `RegistrySnapshot.binding()` is identity data, not evidence of
   a current claim. Add a narrow existing-store guard for the fresh-write lane.
   Its result does not replace human approval or authenticate a hostile app
   running under the same operating-system user.
4. Pass new session bindings explicitly into manifest preparation. Preserve the
   absent extension and original byte/digest contract of historical documents.
   Native/custom adapters must freeze and recheck the same domain plus session
   binding rather than silently rewriting every old context factory.
5. A new capture may reference old intake evidence. Attribute only the new
   capture decision; do not reattribute the intake's creator or approval.
6. Resume from the original context, manifest, reviewer claim and authentication.
   Do not inject the current registry revision into an old approval. Keep
   bootstrap and emergency feedback preservation explicit to avoid requiring a
   working session system before it can itself be installed or diagnosed.
7. Compare actual parser paths and conditional modes against completed adapters
   and narrowly documented exceptions in CI before declaring all-writer scope
   complete. Test aliases, option assignment syntax, repeated-option semantics,
   old approvals, lock waits, interrupted writes and public-output privacy.

## Status

### Approval-free effects are a separate coverage axis

A second bounded source audit confirmed that the approval table is not an
inventory of every filesystem or provider effect. It checked representative
paths, not all 201 approval-unexposed commands.

| Invocation | Observed effect beyond reading |
| --- | --- |
| `index` | Regenerates and commits the shared archive SQLite index without an approval option |
| `index-health` or `staged-cleanup-check`, with `--dry-run --output` | Writes the diagnostic result and operation journal |
| `ai-start-here`, `zet-catalog` or `upgrade-check`, with `--output` | Writes an AI/diagnostic artifact through the shared scratch capture helper |
| `zet-catalog-pass --dry-run` | Writes the required private JSONL output and manages its own incomplete output |
| `doctor --output` or `--progress-log` | Writes a new archive-relative result or an explicitly external progress log |

Do not infer effects from names alone: the ordinary Doctor without output is
read-only, the Notion object-link index is an in-memory projection, SQLite
readers have read-only/sidecar preflight, secure credential verification reads
an existing key without creating one, and upload-verify checks local bytes
rather than proving a remote response. These observations are not a universal
guarantee about all provider or query paths.

The common parser-derived judgment needs an invocation-effect axis independent
of human approval. Preserve exact canonical/alias/argument-mode interpretation;
include generated-index, private-artifact, operational-metadata, credential and
provider effects where actually present. Propagate the validated execution
binding through the shared result-capture and operation-journal boundaries.
Progress records and SQLite temporary files inherit their parent execution;
they do not each demand a new human decision. The shared index remains
archive-wide data even when its generation has a responsible work session.

No-output reads remain available without a session. Historical checkpoints
remain unchanged. Any bootstrap or emergency diagnostic exception must be
explicit and cannot falsely report attribution to a current session. Complete
effect coverage and these output/journal integrations remain acceptance work.

The internal registry decision runner and its three real process-loss/resume
journeys are implemented and development-tested. The complete family mapping,
public CLI/MCP attachment and all-writer enforcement are **not yet complete**.
No existing writer has been closed merely to claim session coverage. No client
archive, provider, credential or feedback ledger was modified by this audit.

See [integration minutes](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).

## Bounded implementation and public query

The pure invocation-effect decision is now implemented in `command_status` for
twelve audited command paths. Parser/handler footprint drift returns unknown
coverage, not an inferred read-only result. Independent review added the explicit
external deferred-input read. The actual CLI attaches the result before its
existing runtime guard; audited index, artifact and journal writes receive that
guard without requiring a new human approval. Unknown coverage does not erase
existing explicit writer guards. This is not yet session binding for every
effect, nor runtime/session enforcement for existing MCP writers.

The one new top-level command, `work-session`, and MCP `archive_work_session`
now share a read-only list/inspect service. Its complete registry generation,
opaque filters, pagination and counts do not infer legacy artifact ownership or
expose labels/claim tokens. Reads may continue while the writer lock is held;
new generations invalidate subsequent cursors rather than mixing snapshots.
Default JSON parse errors are private-safe. The existing no-console startup
reporter is reused; no custom UI or secondary approval system was introduced.

Lifecycle writes and automatic private client-context attachment remain the
next public integration slice. Read-only availability is not evidence that app
registration, work creation, claims or original-operation resume are exposed.
