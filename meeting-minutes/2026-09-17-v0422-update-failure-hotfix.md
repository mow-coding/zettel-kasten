# v0.4.22 update-failure hotfix record (beta letters 161 and 162)

Date: 2026-09-17 (Korea Standard Time)
Status: development verified on synthetic fixtures; release candidate in preparation; not client-verified

Executing model: Claude Fable 5.1 (the user re-enabled Fable 5.1 with
Ultracode for this turn), under the user's standing approval to run the
v0.4.20 to v0.4.24 train and its releases without re-asking. One bounded,
read-only diagnostic workflow (8 reader agents, 22 findings) was used for the
diagnosis; every code change, fixture, verification and release step is solo
and sequential.

## User intent and boundary

Beta letters 161 (main) and 162 (supplement) arrived after the v0.4.21
release: the client's reviewed `project-version-update` to v0.4.21 failed
after the native approval, and even `--resume` failed. The user's reaction was
that an update that cannot even be applied is unacceptable, and asked for it
to be handled. Scope decision: ship the update-failure repair alone as v0.4.22
first, because no v0.4.21 repair reaches the client until the update works;
the rows carried from v0.4.21 (LR-06, LR-02 through LR-05, LR-07, letter 160
② and ④) move to v0.4.23 and later. The session-scope pre-approval that
letter 161 requests (request 6) changes the one-dialog approval contract and is
held for the user's decision. Boundaries unchanged: synthetic archives,
temporary repositories and local bare remotes only; the client workspace and
its letters are read only; no `git add -A`; supplement builds stay under an
ignored directory; every decision is recorded here and in the acceptance
register.

## What the letters report (read only)

- `--approve` reached the runtime-candidate seal and the native dialog, the
  claim was published, and the command failed about nineteen seconds later.
  Diagnostics: `ExactHumanApprovalWorkflowError`,
  `project_version_update_command_failed`, `raw_message_stored: false`, no
  cause. The claim stayed `started`; `version-update.lock` and
  `private/version-updates/update_<ref>/checkpoints.jsonl` (seq 1) remained.
- `--resume` failed in project preflight after about twenty-one seconds.
- `operation-control --action recovery-plan` with the archive root returned
  `operation_not_found`; it worked with the project root.
- `version` flipped `runtime_alignment.reason_code` between
  `project_origin_not_configured`,
  `project_source_tag_not_reachable_from_origin_main` and
  `project_source_observation_unavailable` under disk contention (the shared
  Git probe budget was being exhausted and the skip was mislabeled).
- `upgrade-check --dry-run` produced no output for twenty-three minutes.
- Requests: a distinct budget-exhausted reason, a way to finish or abandon the
  stuck transaction, the exception class and stage in diagnostics,
  operation-control root resolution from the archive root, upgrade-check
  scope documentation, a session-scope pre-approval, and a claim finalizer on
  failure.

## Diagnosis

Confirmed by the read-only workflow and by tracing on a reproduction:

- The post-approval failure is raised inside `_project_update_durable_writer`
  between claim publication and the `approval_bound` checkpoint, in the
  post-claim revalidation of the approved snapshot
  (`_project_update_assert_approved_snapshot_unchanged` / live
  classification). Every catch site on that path re-raises
  `raise _fail(...) from None`, so only the outer class reached the
  diagnostics writer. Directory `st_size` is not the cause in v0.4.21
  (v0.4.19 already zeroed it).
- The claim stays `started` by the one-use contract: a non-success after the
  writer boundary must never be read as clean. No supported path could
  finalize such a claim without a domain write, so the lock and reservation
  could not be released.
- `--resume` reopens the transaction and raises inside reopen/preflight; the
  journal has no stage names after `verify-release`, so it could not say
  where.
- `operation-control` resolves `inspection_root` literally, so an archive
  root cannot find a journal that a project-root run wrote.
- A Git probe skipped by the exhausted budget was reported with an origin or
  tag reason code (no distinct code existed).
- `upgrade-check` is the full deep Doctor, silent without `--progress`, and
  not a documented prerequisite of the update.

The exact stuck state (claim `started`, lock present, checkpoints seq 1) was
reproduced with the released v0.4.21 wheel on a synthetic two-step fixture:
step A installs a v0.4.20 project runtime from a local bare remote, step B
updates it to v0.4.21. The faithful fixture updates cleanly, so the refusing
gate in the client run is load- or state-specific and is not known from the
v0.4.21 diagnostics; the stuck state was produced with a forced writer
failure for the end-to-end verification. A first single-step (fresh install)
reproduction did not fail, which is what established that an existing runtime
is required.

Fixture lesson: the first two-step fixture failed with
`credential_registry_local_profile_not_ignored` because the synthetic archive
lacked `.gitignore` with `profiles/local/`; and its step A used the test-only
memory key while step B used the production key, so the step-A claim failed
authentication during resume discovery. That is a fixture artifact (a client
archive has one production key); the foreign-key claim was removed from the
fixture before the resume-after-abandon verification. Observation recorded,
not changed: resume discovery refuses when any claim in the claims directory
fails authentication, by design.

## Hotfix (branch `claude/v0422-update-failure-hotfix` from main `326eb30f`)

- H1 cause propagation (`exact_human_approval_workflow.py`,
  `exact_human_approval.py`, `archive_cli.py`): the writer boundary raises
  `exact_human_approval_state_unknown` with `cause=failure,
  cause_stage="domain_writer"` and the outer key/claim boundary with
  `cause_stage="key_or_claim"`, still `from None`; `_content_free_cause_code`
  accepts `ProjectRuntimeError` and `ExactHumanApprovalError`; the CLI
  projection carries `cause_code`, `cause_stage` and
  `cause_code_source: fixed_literal_allowlist`, allowing only fixed codes of
  the `project_version_update_`, `project_update_`, `project_runtime_`,
  `project_git_` and `exact_human_approval_` families.
- H2-lite journal stages (`operation_control.py`, `archive_services.py`):
  `materialize-runtime-candidate` (every `project-runtime-candidate-*`
  substage), `native-approval`, `post-claim-revalidate`, `approval-bound`,
  `durable-write`; the durable state carries an observational
  `progress_callback` that never enters a binding, preview, receipt or
  digest. The journal schema is unchanged.
- H3 abandon (`exact_human_approval_workflow.py`, `archive_services.py`,
  `archive_cli.py`): `--resume --abandon-started-approval` calls
  `_abandon_started_exact_human_approved_claims_core`, which finalizes each
  started claim of the exact context as `failed` /
  `operator_abandoned_before_domain_write` only when its authenticated
  checkpoint guard passes, refuses if a succeeded claim exists, and is gated
  by `_project_update_assert_abandon_started_approval_allowed` (journal state
  `exact`, phases `["lock_backlinked"]`, classification `prewrite_exact`;
  otherwise `project_version_update_abandon_unavailable`). The flag without
  `--resume` is `project_version_update_abandon_requires_resume`. Resume
  discovery treats exactly that failure code as absence
  (`_authenticated_claim_failure_code_core`); any other failed claim still
  raises `exact_human_approval_resume_claim_invalid`.
- H4 operation-control root (`archive_cli.py`): `status`, `wait` and
  `recovery-plan` retry once with the parent project root when the archive
  root returns only `operation_not_found`, reporting
  `inspection_root_resolved_to_parent_project`.
- H5 version budget (`archive_services.py`):
  `WOM_KIT_VERSION_GIT_PROBE_BUDGET_SECONDS` 12 → 45;
  `_wom_kit_git_probe_budget_summary()`; `runtime_alignment.reason_code`
  becomes `project_git_probe_budget_exhausted` when a probe was skipped by
  exhaustion.
- H6 upgrade-check notice (`archive_cli.py`): one content-free stderr line
  without `--progress`.

Decisions: no journal schema bump (the fixed cause code and the named stage
answer request 3 without persisting a class name that is not a public code);
the abandon is a resume-only, review-gated, before-mutation-proof path, which
is the "future path" the approval contract reserved terminal `failed` for; no
new approval system; the session-scope pre-approval is not implemented.

## Verification

- `tests/test_v0422_update_failure_hotfix.py`: 10 tests (cause propagation
  and allowlist, journal stage naming, operation-control root retry, abandon
  closes a started claim / leaves guard-rejected claims / refuses with a
  succeeded claim / abandoned claim is absence for discovery while other
  failures still block, budget summary and 45-second floor, upgrade-check
  notice). Passed with the approval-workflow, project-update-transaction,
  invocation-dispatch and operation-control-availability cohorts (263 tests)
  during development; the wider cohorts are rerun for the candidate.
- End to end on the hotfix wheel against the reproduced stuck fixture: the
  forced writer failure produced `cause_code=
  project_version_update_approved_snapshot_unavailable`,
  `cause_stage=domain_writer`, `cause_code_source=fixed_literal_allowlist`
  and journal stages through `native-approval`; `--resume
  --abandon-started-approval` marked the claim `failed` /
  `operator_abandoned_before_domain_write`; the following plain `--resume`
  returned `preapproval_scaffold_cancelled` with the lock removed, the
  transaction directory cleared and the pin still v0.4.20; a fresh
  `--approve` reached `updated_restart_required` with the pin at v0.4.21 and
  one succeeded claim.
- The released v0.4.21 wheel reproduces the stuck state on the same fixture,
  which is the negative control.

## Release preparation

Version bump to 0.4.22 mirrors the v0.4.21 bump: supply lock
`project-runtime-supply-lock-v0.4.22.json` (SHA-256
`523d1704eed602a49ae3e1cbebe9cb49eb6a2586a53e40da5e549891eb07655e`), policy
and `project_runtime.py` digest, packaged release note and manifest
(`sync_package_resources.py`), bootstrap blocks, status ladders, historical
release-doc test pins, `test_v0422_release_docs.py`, CHANGELOG, UPGRADE (EN
and KO), READMEs, and the doc paragraphs for the contract, operation control,
version truth and the philosophy evidence. The register gains row UF-01 and
two execution-log entries. Attribution of the release commits: Claude Fable
5.1.

## Release candidate (PR #104)

[PR #104](https://github.com/mow-coding/zettel-kasten/pull/104) carries the
hotfix, the bump and two candidate-CI corrections. The first candidate run
found, on the Ubuntu shards, that the merged-stream CLI test runner parses
stdout and stderr as one JSON document (the new `upgrade-check` notice is now
printed only when stderr is a terminal, so scripted and JSON consumers keep
their exact bytes) and that the v0.4.20 cause-allowlist test expected an
in-family but unlisted token to be dropped (the v0.4.22 contract carries
fixed tokens of the project-update and approval families, all literal in
source; the test's unlisted case now uses an out-of-family token). The
second run passed every shard except Windows shard 4/4, which was cut at its
45-minute budget with no failing test (the v0.4.21 candidate took 40.7
minutes on the same shard; every Windows shard ran 6-10% slower today), so
that budget is raised to 60 minutes in the workflow. Records: the register's
"v0.4.22 release candidate" entry.

## Client boundary

Nothing here sets any letter's `resolved_in`. After v0.4.22 is public the
client AI must install the v0.4.22 bootstrap wheel, run
`project-version-update <project-root> --resume --abandon-started-approval
--affirm-external-writers-quiescent` and then the plain `--resume` with the
bootstrap `archive` to release the reservation, then one reviewed
`--dry-run` and `--approve` to v0.4.22; if that run fails again, its
`cause_code`, `cause_stage` and journal stage are the evidence the next
letter should carry.
