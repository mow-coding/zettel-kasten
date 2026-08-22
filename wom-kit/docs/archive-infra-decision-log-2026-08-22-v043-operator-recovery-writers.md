# Decision Log: v0.4.3 Operator Recovery Writers

Date: 2026-08-22

## Context

The current product had safe observation and prevention surfaces but left
three practical operator gaps: a wrong draft feedback body could not be
corrected under its stable id, the project-local source mirror updater was
fixed closed, and Windows could silently select an older `archive` launcher
while source provenance checks waited on Git.

## Decision

Reopen only the narrow existing command families:

1. Extend `operator-feedback-compose` with draft-only body-hash CAS revision
   and immutable-status supersession. Preserve the old body before atomic
   replacement, publish create-only revision evidence, and use the existing
   metadata command for a fresh-SHA draft rebind. Never revise a delivered,
   acknowledged, resolved, or archived body in place.
2. Move `project-version-update` from the fixed-close inventory to an
   operation-specific exact-human binding. Derive a fresh content-free preview
   in the CLI and again in the service, authenticate the one-use claim against
   the same plan and target, then reuse the existing locked updater. Do not
   reopen collision mutation or bytecode repair.
3. Extend `archive version`, not the top-level command surface, with a capped
   non-executing Windows PATH candidate probe, explicit launcher/module/project
   provenance boundaries, immediate content-free progress, and one 12-second
   total Git-read budget.

Keep lifecycle `delivered` and `external_submission_performed` independent.
An internally delivered record with external submission false is still
immutable. Tests use synthetic status relationships rather than real beta
letter content.

## Consequences

Operators gain executable correction and update paths without parallel public
machinery. The fixed-close inventory decreases from 78 to 77 and
operation-specific approval availability increases by one; top-level command
count is unchanged.

Feedback revision is intentionally two authority steps: body transaction, then
metadata rebind. A body revision result therefore routes immediately to the
fresh record-SHA rebind, and full verification is complete only after that
second step succeeds. Old bytes and transition evidence remain immutable.

The updater's current exact-human receipt is returned alongside the existing
project-update receipt. The older updater transaction remains the write and
rollback authority; future integration may add an explicit durable cross-link
between those receipts, but must not weaken either verification boundary.

PATH diagnosis is observational. It never executes an alternate launcher,
changes PATH, infers an alternate module import, or treats an installed version
label as proof of the running process. Deadline exhaustion makes provenance
incomplete and nonzero rather than hanging or claiming alignment.
