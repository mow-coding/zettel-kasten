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

The internal registry decision runner and its three real process-loss/resume
journeys are implemented and development-tested. The complete family mapping,
public CLI/MCP attachment and all-writer enforcement are **not yet complete**.
No existing writer has been closed merely to claim session coverage. No client
archive, provider, credential or feedback ledger was modified by this audit.

See [integration minutes](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).
