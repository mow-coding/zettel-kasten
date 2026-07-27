# Archive Infra Decision Log - v0.3.267 Abstract Recovery Executor

Date: 2026-07-28

Status: accepted for implementation and release-candidate verification

## Context

v0.3.265 made interrupted abstract apply and revert batches observable through
durable transaction journals. v0.3.266 added a bounded read-only planner with
one fixed action for each safe journal state. Canonical recovery remained
unimplemented.

The executor must not turn a recommendation into broad automatic authority. A
retained lock proves that cleanup did not complete; it does not prove that the
original process is dead. A basis SHA alone also does not bind the current
plan, participant state, or approved action.

## Decision

Add one single-case CLI executor:

```text
archive zet-abstract-backfill-recover <archive-root> \
  --operation <apply|revert> \
  --basis-sha256 <sha256:...> \
  --expected-plan-digest <sha256:...> \
  --expected-action <fixed-action> \
  --dry-run
```

Alias:

```text
archive abstract-backfill-recover
```

The same command uses `--approve`, a safe reviewer id,
`--affirm-recovery-reviewed`, and `--affirm-archive-quiescent` for a write.
Exactly one of `--dry-run` and `--approve` is allowed.

The executor reruns the complete bounded recovery plan while holding a local
OS advisory recovery guard. It proceeds only when the complete plan digest,
operation, basis SHA-256, observed case, expected fixed action, final receipt
state, and current participant hashes still agree.

## Recovery Matrix

- `cleanup_unstarted_transaction_evidence`: no canonical or receipt write;
  remove only the matching basis lock and journal.
- `rollback_uncommitted_apply_to_before`: deterministically remove only the
  inserted abstracts from participants at their recorded after hash, verify all
  recorded before hashes, then remove matching evidence.
- `resume_revert_forward_and_finalize_receipt`: deterministically remove the
  abstract from participants still at the recorded before hash, verify every
  after hash, create and verify the deterministic revert receipt, then remove
  matching evidence.
- `finalize_revert_receipt`: verify every participant already has its recorded
  after hash, create and verify the deterministic revert receipt, then remove
  matching evidence.
- `cleanup_verified_completed_evidence`: rely on the fresh complete receipt
  lifecycle verification, then remove only the matching basis lock and journal.
- `manual_forensic_hold`: never executable.

## Failure And Retry

The original transaction journal remains the recovery progress record.
Recovery moves only in the fixed safe direction. It does not undo successful
recovery writes when a later participant or receipt step fails.

If a recovery run stops or fails:

- the journal is retained;
- the basis lock is retained;
- current participant hashes expose the new progress point;
- the operator must generate a new plan and provide a fresh digest/action and
  fresh approval.

A fully written and verified revert receipt is committed evidence. If cleanup
then stops, the next plan classifies the case as verified completed residue and
permits cleanup only.

## Concurrency Boundary

A local OS advisory guard serializes recovery executor processes. A missing
basis lock is atomically reacquired before any canonical or receipt mutation.

This release does not claim:

- exclusion of external editors;
- exclusion of WOM versions that do not implement the recovery guard;
- cross-basis serialization for ordinary apply/revert writers;
- automatic proof that an old process is dead.

Therefore write approval additionally requires the operator to affirm that the
original process has stopped and the archive is quiescent. Cross-basis
ordinary-writer serialization remains a separate design track.

## Privacy Boundary

The public result may expose the operation, basis SHA-256, plan digest, fixed
action, participant counts and content hashes already present in the planner,
and boolean write/cleanup outcomes. It must not echo journal or receipt paths,
zettel ids or paths, reviewer identity, proposal filename, body or abstract
text, journal digest, lock content, or absolute local paths.

The executor calls no model, provider, network, environment credential, or
secret store.

## Release-Candidate Verification

The complete local release candidate passed:

- 34 abstract-backfill regression tests;
- 121 documentation contract tests and 3,409 documentation subtests;
- all four public release-readiness checks;
- the full repository suite with 1,561 passed, 13 skipped, and 4,268
  subtests;
- a clean isolated v0.3.267 wheel install with 93 packaged resources,
  runtime-skill lifecycle, onboarding, and strict Doctor green.

The isolated wheel SHA-256 was
`3b56d32fe75b7e054413c6edf86df1252784d4914b5dade54d0e797330d4fa89`.
Remote CI, tag, GitHub Release, attached-wheel identity, and public reinstall
remain release-supervisor checks after the release commit exists.
