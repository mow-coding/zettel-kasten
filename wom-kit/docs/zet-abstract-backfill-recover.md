# zet Abstract Backfill Recovery Executor

Historical v0.3 record — Status: implemented as a single-case approval-gated CLI writer in v0.3.267

Current v0.4.0 boundary: the recovery plan and executor dry-run remain
available. Approval returns `compound_exact_human_approval_binding_required`
before private target read or mutation and changes no canonical, receipt,
journal, lock, or recovery guard. The executor details below are historical
v0.3 semantics, not current write authority.

## Purpose

`zet-abstract-backfill-recovery-plan` classifies every retained abstract apply
or revert transaction journal and assigns one fixed action. The executor turns
exactly one reviewed non-forensic case into a bounded write or evidence cleanup.

It is not automatic startup repair. A plan, a basis SHA-256, and an action do
not by themselves grant write authority.

## Preview

First run the complete read-only planner:

```text
archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-cases 100 --progress --format json
```

Select one case and preview the exact executor binding:

```text
archive zet-abstract-backfill-recover <archive-root> \
  --operation <apply|revert> \
  --basis-sha256 <case.basis_sha256> \
  --expected-plan-digest <plan.plan_digest> \
  --expected-action <case.recommended_action> \
  --dry-run --max-receipts 5000 --max-locks 5000 --max-cases 100 \
  --progress --format json
```

Alias:

```text
archive abstract-backfill-recover
```

A successful preview returns `ready_to_recover` and writes nothing.

## Current v0.4.0 Approval Boundary

Do not continue past preview. Approval is fixed fail-closed with
`compound_exact_human_approval_binding_required`. Historical v0.3 recovery
required the following evidence, but those values do not grant current
authority:

- a complete, untruncated receipt/lock/journal audit;
- the same complete recovery-plan digest;
- the same operation and basis SHA-256;
- the same fixed action;
- a fresh current-hash classification;
- no missing or divergent participant;
- no unsafe lock path;
- no occupied but unverified deterministic final receipt;
- a privacy-safe reviewer id;
- both explicit affirmations.

`manual_forensic_hold` is never executable.

## Executable Actions

| Action | Canonical writes | Receipt write | Cleanup |
| --- | ---: | ---: | --- |
| `cleanup_unstarted_transaction_evidence` | 0 | 0 | matching basis lock and journal |
| `rollback_uncommitted_apply_to_before` | only participants still at recorded after hash | 0 | after every participant verifies at before hash |
| `resume_revert_forward_and_finalize_receipt` | only participants still at recorded before hash | 1 deterministic revert receipt | after receipt verification |
| `finalize_revert_receipt` | 0 | 1 deterministic revert receipt | after receipt verification |
| `cleanup_verified_completed_evidence` | 0 | 0 | matching basis lock and journal |

An apply rollback removes only the deterministic inserted abstract line and
must reproduce the journaled full-file before hash. Revert recovery moves
forward because the removed private abstract text is intentionally absent from
both the transaction journal and the receipts.

## Failure And Retry

The original transaction journal is the recovery progress record.

Before the first recovery write, every required target byte sequence is
materialized and checked. Immediately before each write, the source bytes are
checked again. Each successful write is checked against its exact target hash.

If an ordinary failure or forced process exit happens later:

- already completed safe-direction recovery writes are not reversed;
- the transaction journal remains;
- the basis lock remains;
- no incomplete final receipt is treated as committed;
- a new plan reports the participant hashes at the new progress point;
- a new complete plan digest and new approval are required.

A fully written revert receipt is verified before evidence cleanup. If the
process stops after the receipt commits, the next plan reports
`cleanup_verified_completed_evidence`.

This differs from the ordinary non-recovery revert transaction, whose handled
in-process failures restore the applied state. Recovery-produced revert
receipts therefore record `rollback_on_runtime_failure: false`.

## Concurrency Boundary

Recovery executor processes share a local OS advisory guard. The guard is
automatically released when the process exits, including a hard exit. A missing
basis lock is atomically recreated before canonical or receipt mutation.

These mechanisms coordinate the v0.3.267 recovery executor. They do not lock:

- external editors or sync tools;
- older WOM versions;
- ordinary apply/revert transactions with a different basis;
- unrelated multi-zet writers.

That is why `--affirm-archive-quiescent` is mandatory. It is an explicit
operator statement, not something WOM infers from a stale lock file.

## Compatibility Boundary

Recovery-produced revert receipts use the existing v0.1 receipt identity but
truthfully set `mutation_contract.rollback_on_runtime_failure` to `false`.
v0.3.267 relaxes that schema field from `const: true` to a boolean.

Existing receipts with `true` remain valid. WOM-kit v0.3.266 and older reject a
new recovery-produced receipt as schema-invalid, so after this executor creates
one, keep WOM-kit v0.3.267 or newer for receipt audit. This is a one-way reader
compatibility gate, not a preference.

## Privacy Boundary

The executor may read private journal ids, canonical paths, prior reviewer
metadata, receipt metadata, and canonical bytes needed for exact hash checks.
Its result does not echo:

- journal or receipt paths;
- zet ids or paths;
- title, body, or abstract text;
- reviewer identity;
- proposal filename;
- journal digest;
- lock content;
- absolute local paths.

It calls no model, provider, network, database, environment credential, or
secret store.
