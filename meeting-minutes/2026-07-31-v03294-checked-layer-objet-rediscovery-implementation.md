# v0.3.294 Checked-Layer Objet Rediscovery Implementation

Date: 2026-07-31

## User Intent

Continue the accumulated beta-feedback work in small, verifiable releases.
The immediate failure is an AI turning a generated-index zero result into a
false global conclusion that an original file or objet does not exist. The
user explicitly asked for careful ongoing implementation and release
preparation rather than another speculative stop.

## Authority And Scope

The implementation followed Letter 105, its intake record, the accepted
v0.3.293-v0.3.299 release-train decision, and the dedicated v0.3.294
implementation directive.

This batch is limited to a read-only checked-layer rediscovery evidence plan.
It does not implement the v0.3.295 private original-name contract, v0.3.296
private metadata registration/finder, v0.3.297 approved external-local-store
lifecycle, v0.3.298 exact external resolver, or v0.3.299 source-reference
coverage.

No command was run against the beta archive. No beta letter, user archive, or
existing external directory was read or changed. No provider API, credential
store, or beta-system network operation was used. The independent audit did
consult the public SQLite locking and URI documentation read-only, and safety
regressions used only synthetic temporary archives, SQLite files, WAL/journal
sidecars, and an automatically removed temporary external-directory junction.

## Implementation Chronology

1. Read the project agent rules, v0.3.294 directive, Letter 105, release-train
   decision, intake record, and v0.3.293 implementation record in full.
2. Inspected ordinary `search_archive`, index-health, CLI parser, MCP tool
   registration, runtime action routing, Runtime Skill sources, package
   synchronization, and predecessor tests.
3. Added the shared
   `wom-kit/objet-rediscovery-plan/v0.1` service result, ten fixed layer IDs,
   content-free blocked builder, privacy flags, and closed-action flags.
4. Added CLI `objet-rediscovery-plan` and MCP
   `objet_rediscovery_plan`, both using the shared service.
5. Preserved ordinary `search.complete == not truncated` and projected only
   safe index counts and state labels. Raw query and result rows are discarded
   before result construction.
6. Advanced action routing to v0.8 with
   `plan_objet_rediscovery_before_negative_claim` while retaining the v0.3.293
   operator-feedback and readiness packet.
7. Updated Runtime Skill guidance so an AI must run the rediscovery plan
   before a global absence claim.
8. An independent read-only baseline audit caught two important overclaim
   risks:
   - index-health checks zettel path/id/status/kind/mtime boundaries, not
     searchable title/body or non-zettel source freshness; all five search
     channels were therefore changed to snapshot-only evidence with
     `freshness_proven: false`;
   - ordinary SQLite reads can create WAL/SHM sidecars, while immutable reads
     can ignore pending WAL content.
9. Added a plan-private immutable SQLite connector, blocked non-empty WAL
   content, and compared main-index snapshot state before and after health and
   search reads. Ordinary search's connector, transaction, public signature,
   and result schema remain unchanged.
10. Added focused tests for zero matches, candidates, truncation/count-total,
    stale and malformed indexes, permission/decoder errors, WAL and concurrent
    snapshot change, privacy, zero writes/calls, CLI/MCP parity, capabilities,
    routing, feedback sequence, and readiness preservation.
11. Added public documentation, decision/release/upgrade/change records,
    current-version surfaces, and packaged Runtime Skill source updates.
12. The independent implementation audit then reproduced and corrected seven
    contract gaps before final regression:
    - the top-level unchecked/unavailable count included five
      `checked_snapshot_only` index layers and reported 10 instead of 5;
    - malformed BLOB-typed SQLite text could let `TypeError` escape instead of
      returning the fixed private blocked result;
    - global early truncation could skip later index channels while marking all
      five channels checked;
    - the non-exact checked-match count included only globally returned rows
      instead of the bounded lower bound proven by all channel probes;
    - immutable SQLite could ignore a non-empty rollback journal as well as a
      pending WAL;
    - ordinary `Path.rglob` could descend a Windows junction before its escaped
      result was filtered, contradicting the no-external-scan claim; and
    - an empty schema-valid MCP query was rejected before the shared service,
      breaking CLI/MCP blocked-result parity.
13. The corrections now independently probe every SQLite search channel with
    a bounded `limit + 1` query, block unavailable channel schema, validate
    global/per-channel count consistency, catch typed-column failures without
    private output, block non-empty or unsafe WAL/rollback-journal sidecars,
    and use a no-reparse local zettel walker for this plan while leaving
    ordinary search and index-health behavior unchanged.
14. The rollback-journal decision was strengthened after the audit consulted
    SQLite's primary locking and URI documentation: ordinary readers can
    perform hot-journal recovery, while `immutable=1` deliberately skips
    locking/change detection. A non-empty rollback journal is therefore
    anomalous evidence and fails closed.
15. A local editable-install path initially caused some test commands to
    import an older main-worktree package. Those results were explicitly
    discarded. Every accepted final regression sets `PYTHONPATH` to this
    worktree's `wom-kit/src` and first verifies version `0.3.294` plus the exact
    module path.

## Agent Provenance Boundary

The work ran in a Codex desktop implementation task with a separate Codex
read-only design-audit subtask. No platform-signed served-model attestation was
exposed to this task, so this record does not attribute either role to a more
specific hidden backend model. Role, task, code, diff, test, and Git evidence
are recorded; an unexposed backend identity is not guessed.

## AI Contribution Observation

### Implementation Role

- observed product/app: Codex desktop app task environment, as identified by
  the task's provided app context;
- runtime self-report: Codex implementation agent;
- task role: implement, test, document, and locally commit the v0.3.294
  checked-layer objet rediscovery batch in the dedicated worktree;
- UI model label observed by this agent: `not_observed`;
- served model ID or platform attestation exposed to this agent:
  `not_exposed`;
- inference telemetry, service tier, or backend routing exposed:
  `not_exposed`;
- model transition or fallback observed in this task: `not_observed`;
- input commit: `f8e209f21179a769bde3abf0526473b2ea5d41fd`;
- implementation output commit: pending the final local implementation commit;
- test reference: exact-worktree focused, ordinary-regression, non-CLI, CLI,
  release-readiness, and clean-wheel evidence recorded in this file;
- human authority: the human project owner and release supervisor retain final
  scope, merge, release, and beta-validation authority. This AI role does not
  authorize a push, PR, tag, or release.

### Independent Read-Only Audit Role

- observed product/app: separate Codex collaboration subtask inside the same
  desktop project context;
- runtime self-report: Codex read-only design and implementation auditor task
  `/root/v03293_299_backlog_map/v03294_design_audit`;
- task role: independently inspect the directive, implementation diff,
  privacy/fail-closed boundaries, SQLite behavior, tests, package resources,
  and durable record without editing the worktree;
- served-model UI label, telemetry, model ID, or platform attestation exposed
  to the auditor: `not_exposed`;
- model transition or fallback observed by the auditor: `not_observed`;
- review input: input commit
  `f8e209f21179a769bde3abf0526473b2ea5d41fd` plus the evolving uncommitted
  v0.3.294 worktree diff on branch
  `codex/v0.3.294-checked-layer-rediscovery`;
- review output commit: none; the audit role was read-only;
- review reference: collaboration task `v03294_design_audit`, whose concrete
  reproductions and corrections are listed in the implementation chronology;
  its final clear covered 11 exact-source focused tests, custom sidecar
  boundary probes, compilation, diff checks, and selected package/runtime
  regressions;
- human authority: findings are advisory evidence. The human project owner and
  release supervisor retain final acceptance and public-release authority.

## Verification Record

Early exploratory test output is not release evidence because the editable
import-path contamination was discovered afterward and those runs were
discarded.

Accepted exact-worktree verification:

- import preflight: version `0.3.294` and
  `zettel-kasten-v03294/wom-kit/src/wom_kit/archive_services.py`;
- focused rediscovery regressions: 11 passed, including real Windows junction,
  rollback-journal, later-channel-unavailable, BLOB, and CLI/MCP empty-query
  cases;
- capability/runtime/package documentation group: 170 passed;
- ordinary search and MCP search targeted checks: 7 passed;
- corrected ordinary index-health targeted checks: 5 passed;
- exact-final-tree non-CLI suite: 548 tests passed, 14 skipped, 0 failed;
- exact-final-tree CLI suite: 1,349 tests passed, 8 skipped, 0 failed;
- release-readiness gate: 4/4 passed (public link hygiene, Korean product
  language, public privacy, and packaged Runtime Skill);
- clean wheel-only installation:
  `wom_kit-0.3.294-py3-none-any.whl`, 120 wheel files, all 103 manifested
  resources verified (333,681 bytes), all four entry points exercised,
  Runtime Skill lifecycle passed, onboarding preview/write passed, strict
  Doctor passed, and SHA-256
  `948b496f1400a896373d565a962c2ba65f84c54ab2209fd67b4a509f762e2c17`;
- Python compilation and `git diff --check`: passed after the focused fixes;
- independent audit disposition: clear after all seven concrete findings were
  reproduced, corrected, and rechecked.

One attempted wheel check was discarded because the source-test
`PYTHONPATH` override was mistakenly left enabled, so the check correctly
reported that its installed-version probe was not package-only. The accepted
wheel result above was then produced without that override in the tool's
isolated wheel-only environment.

## Release Boundary

The branch began from local commit
`f8e209f21179a769bde3abf0526473b2ea5d41fd`. That commit is not asserted to be
the exact public v0.3.293 merge predecessor. Before public release, the release
supervisor must identify the exact merged public v0.3.293 commit, rebase this
candidate onto it, resolve conflicts, and rerun the full suite and clean-wheel
verification.

No push, PR, tag, GitHub Release, anonymous download, or beta validation is
performed in this implementation batch.
