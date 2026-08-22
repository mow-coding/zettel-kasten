# v0.4.3 Operator Recovery Writers — Implementation Minutes

Date: 2026-08-22

## Objective and correction

Recent beta feedback made the gap clear: preventing a repeat is not enough
when the operator still cannot correct an existing draft, update a stale
project mirror, or tell which Windows `archive` installation is actually
running. The implementation therefore had to deliver narrow executable paths,
not another family of plan-only commands. No new top-level CLI command was
allowed.

The corrected feedback facts used by this implementation are lifecycle-only
synthetic fixtures: 141 and 143 are archived, 142 remains independent, and
144 is delivered internally while external submission remains false. The
implementation does not copy client letter bodies or private paths into public
tests.

## Plan and feedback loop

1. Reuse `operator-feedback-compose` and the existing metadata record writer
   for a draft-only same-id correction.
2. Reuse the exact-human approval broker and the existing v0.3 project updater
   core instead of adding a parallel updater.
3. Extend `archive version` with bounded Windows launcher provenance and early
   progress instead of adding another diagnostic command.
4. Run focused tests after each vertical slice, then run the affected approval,
   feedback, version, documentation, and historical fixed-close regressions.

The first feedback-body slice proved body CAS and immutable prior evidence but
left the metadata record temporarily bound to the old body. A vertical test was
then added and the existing `operator-feedback-record --intent update` path was
narrowly reopened for verified draft-to-draft managed-body rebind. Delivered,
acknowledged, resolved, and archived records remain immutable; corrections use
a new id plus an explicit supersession receipt.

The first deadline regression used a short sleep and was flaky on Windows timer
granularity. It was corrected to move the injected test deadline explicitly
into the past, making the assertion deterministic.

## Implemented protocol

### Draft feedback revision

- `operator-feedback-compose --intent revise` requires the exact current body
  SHA-256 and the normal exact reviewed plan digest.
- The planner binds the current draft record SHA, current feedback reference,
  body SHA, request SHA, and proposed body SHA.
- The writer shares the metadata writer's per-feedback cross-process lock,
  revalidates lifecycle and CAS state, preserves old bytes create-only, replaces
  the body atomically, and writes an immutable transition receipt.
- The existing metadata record writer accepts a changed `feedback_ref` only
  when both current and proposed status are `draft` and the new managed body and
  receipt pass two stable checks. A fresh record SHA is still required.
- `--intent supersede` creates a new body and immutable link receipt while
  proving the old record/body stayed unchanged.

### Project version update

- `project-version-update` remains the same top-level command.
- Dry-run now exposes an operation-specific exact-human binding.
- CLI approval derives the binding, opens the native approval workflow, and
  passes only the authenticated one-use claim and exact digests to the service.
- The service rejects unbound calls before private project reads, derives the
  preview again, requires exact plan/target equality, authenticates the claim,
  and only then invokes the existing updater.
- The existing updater retains its own quiescence, lock, checkpoint, Git tag and
  origin, materialization, rollback, pin, and durable receipt gates.
- Collision mutation and bytecode repair remain fixed closed.

### Windows PATH and source provenance

- `archive version --progress` emits a content-free first line immediately and
  5-second heartbeats.
- A capped `System32\\where.exe archive` probe enumerates at most 64 candidates
  without executing alternates and identifies selection order and observable
  current-launcher mismatch.
- `path_shadow_diagnostic` separately reports imported module version/origin and
  inspected project source version, and states that alternate launcher-module
  bindings are not inferred.
- Paths remain redacted unless `--no-redact-local-paths` is explicit.
- Every Git read in one version inspection shares a 12-second total deadline;
  later reads are skipped after exhaustion, with no writer started.

## Files and verification

Implementation touched the existing CLI, service, exact approval binding,
feedback body module, focused tests, and the public operator/version documents.
No Basoon archive, beta-letter source, other worktree, PATH entry, external
provider, or release state was changed.

Focused verification covers body create/revise/supersede, immutable lifecycle
states, vertical metadata rebind, exact project-update approval and replay,
PATH ordering/redaction, immediate progress, silent-child timeout, shared Git
deadline, parser fixed-close inventory, and historical v0.4.0 publication
truth. Final commit and integration test results are recorded in the task
handoff; this source implementation is not itself a merged tag or public
release.
