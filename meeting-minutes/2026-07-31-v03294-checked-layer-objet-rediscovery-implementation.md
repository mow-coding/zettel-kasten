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
16. The candidate was rebased onto the exact annotated-v0.3.293 target,
    public merge commit `52e01286ee1aff93f245e12b0dc33999a2b312c7`.
    All following evidence is from that exact-predecessor history, not the
    earlier local base.
17. Post-rebase review separated exact and bounded rediscovery counts.
    `checked_match_count_exact` now makes the distinction machine-readable,
    and neither count form upgrades incomplete evidence into a negative claim.
18. Public privacy hygiene was widened to inspect Git-tracked meeting minutes
    and decision logs even when a broad ignore rule also matches them. Four
    historical real-home-path examples were replaced by explicit placeholders.
19. The no-reparse zettel walk was strengthened into a held directory/file
    snapshot. Strict rediscovery consumes the captured relative path,
    frontmatter, and mtime without reopening a checked path; missing, zero, or
    changed Windows file identities, decoder failure, file replacement,
    directory replacement, and junction escape all fail closed.
20. Health, global search, and five channel probes now share one immutable
    SQLite connection and one explicitly pinned read transaction. Borrowed
    helpers cannot reconnect, begin, roll back, or close; nested cleanup still
    closes the connection if rollback itself fails.
21. The external-evidence layer was corrected from `not_implemented` to
    `unchecked`/`unknown`. WOM already has the query-independent read-only
    `archive backup-evidence <archive-root> --dry-run` status, so the plan names
    that static next command without pretending it was executed.
22. Release wheel verification was upgraded from checking executable presence
    to actually executing both CLI version probes and full
    initialize/list/EOF handshakes for both MCP aliases. The checker requires
    strict UTF-8, empty stderr, bounded output and runtime, complete
    byte-identical MCP inventories, a sanitized Python environment, and
    fail-closed descendant-process containment on Windows and POSIX.
23. Independent review found and closed the wheel checker's final scheduling
    race: output overflow is now recomputed after both reader joins. A
    deterministic delayed-reader regression proves that a valid JSON prefix
    plus excess bytes cannot pass only because the parent process exited first.

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
- exact public predecessor:
  `52e01286ee1aff93f245e12b0dc33999a2b312c7`;
- initial post-rebase documentation/provenance commit:
  `02a55180980f84186b73127147eacfe4e8cfe2cd`;
- implementation commits through the final code correction:
  `72af9e1e4076dda41295559f9eec665dbb7bde7b`,
  `92a565bc8609f1194eebf825ca980bef0d883385`,
  `d9d784ba0020a28f5b835cd1758b1e45270e608f`,
  `9f68000ac5f0481441d65ea0ef6ca7ddeece1f54`,
  `1c47f876c0a3d99b274ff416e39cc180c3f0ed1c`,
  `301f5c33b014ef19d7baab40f9c6fa8e20ef2782`, and
  `9ca42388347174dfa453045a9008a0ae8e8b73f8`;
- provenance/evidence follow-up commit: the SHA of the commit containing this
  final record is captured by Git and the release-supervisor handoff rather
  than self-referenced inside its own body;
- test reference: exact-worktree focused, ordinary-regression, documentation,
  package-resource, release-readiness, complete source-suite, and pre-PR
  clean-wheel evidence recorded in this file; exact-merge/public-artifact
  evidence remains explicitly pending;
- human authority: the human project owner and release supervisor retain final
  scope, merge, release, and beta-validation authority. This AI role does not
  authorize a push, PR, tag, or release.

### Collaborating Implementation And Review Role

- observed product/app: separate Codex collaboration subtask inside the same
  desktop project context;
- runtime self-report: Codex implementation and follow-up review task
  `/root/v03294_privacy_impl`;
- task role: implement the public-privacy tracked-record changes, placeholder
  corrections, tests, and related privacy/readiness documentation, then
  independently review the root-authored installed-wheel checker,
  descendant-containment, and bounded-reader behavior;
- served-model UI label, telemetry, model ID, or platform attestation exposed:
  `not_exposed`;
- model transition or fallback observed: `not_observed`;
- contribution integration: the direct implementation is included in commit
  `d9d784ba0020a28f5b835cd1758b1e45270e608f`; read-only wheel-review findings
  were reproduced and corrected by root in
  `9ca42388347174dfa453045a9008a0ae8e8b73f8`;
- review outcome: independently reproduced concrete descendant and
  delayed-reader overflow gaps, then returned `CLEAR` after root's integrated
  fixes;
- human authority: the human project owner and release supervisor retain final
  acceptance and public-release authority.

### Independent Read-Only Audit Roles

- observed product/app: separate Codex collaboration subtasks inside the same
  desktop project context;
- runtime self-report: Codex read-only design, snapshot/TOCTOU, and SQLite
  lifecycle audit roles;
- review references: the earlier `v03294_design_audit` plus current
  `/root/v03294_snapshot_review` and `/root/v03294_sqlite_design` tasks;
- task role: independently inspect privacy/fail-closed boundaries, held local
  snapshots, one-transaction SQLite behavior, tests, package resources, and
  durable records without changing the accepted implementation;
- served-model UI labels, telemetry, model IDs, or platform attestations
  exposed to these auditors: `not_exposed`;
- model transitions or fallbacks observed by these auditors: `not_observed`;
- review input: exact public predecessor plus the evolving v0.3.294 branch
  `codex/v0.3.294-checked-layer-rediscovery`;
- review output commits: none; the listed audit roles were read-only;
- concrete review outcome: snapshot/TOCTOU and one-transaction SQLite reviews
  returned `CLEAR`;
- human authority: findings are advisory evidence. The human project owner and
  release supervisor retain final acceptance and public-release authority.

## Verification Record

Early exploratory test output is not release evidence because the editable
import-path contamination was discovered afterward and those runs were
discarded.

Accepted exact-worktree verification after the exact-v0.3.293 rebase:

- import preflight: version `0.3.294` and
  repository-relative module `wom-kit/src/wom_kit/archive_services.py`;
- focused rediscovery regressions: 21 passed with 10 subtests, including held Windows identity,
  file/directory replacement, junction, strict decoder, one SQLite
  transaction, rollback cleanup, sidecar, unavailable-channel, BLOB, and
  CLI/MCP parity cases;
- installed-wheel checker regressions: 33 passed with 80 subtests, including environment
  isolation, bounded output, delayed-reader overflow, inherited-pipe timeout,
  detached descendant, Windows Job Object, strict CLI/MCP parsing, and exact
  resource-integrity cases;
- public privacy hygiene regressions: 15 passed with 32 subtests, including Git-tracked ignored
  records and non-placeholder Windows/POSIX home paths;
- corrected ordinary index-health targeted checks: 4 passed;
- capability/runtime/package documentation group: 149 passed;
- release-readiness gate: 4/4 passed (public link hygiene, Korean product
  language, public privacy, and packaged Runtime Skill);
- package-resource synchronization: 103/103 current;
- complete Windows source suite: 1,929 tests run in 1,415.677 seconds;
  1,907 passed, 22 skipped, and 0 failed;
- clean pre-PR wheel-only installation from source commit `098f65bf`:
  `wom_kit-0.3.294-py3-none-any.whl`, 1,258,146 bytes, SHA-256
  `efab0dc2f5bebf7614a00c7b9e2499be3e74c1986934eb40db3b2a1b65c60bd5`,
  120 wheel files, and 103/103 resources totaling 337,673 bytes;
- installed entrypoint evidence: both CLI aliases reported v0.3.294 with empty
  stderr; both MCP aliases completed initialize/initialized/tools-list/EOF,
  exposed 121 tools, and produced the same 100,970-byte canonical inventory
  SHA-256
  `bbf0dae19380438ec6486d256647a9a2d50355c1d8ae85aea3145e9146f6d7bd`;
- installed Runtime Skill lifecycle, onboarding preview/write, and strict
  Doctor all passed; a second fresh virtual environment resolved
  `PyYAML==6.0.3`, installed the preserved wheel, and returned
  `No broken requirements found` from `pip check`;
- this pre-PR wheel is candidate evidence only. The exact public merge commit
  must produce a newly reviewed release wheel before tagging and publication;
- Python compilation and `git diff --check`: passed after the focused fixes;
- independent audit disposition: clear after all concrete findings were
  reproduced, corrected, and rechecked.

One earlier wheel attempt was discarded because the source-test `PYTHONPATH`
override was mistakenly left enabled, so the check correctly reported that
its installed-version probe was not package-only. The accepted pre-PR candidate
result above was produced after removing that override. It does not replace the
mandatory rebuild from the future exact public merge commit.

## Release Boundary

The branch now descends directly from exact public v0.3.293 merge commit
`52e01286ee1aff93f245e12b0dc33999a2b312c7`. That predecessor correction is
complete.

Source success is still not a public-release claim. Push, PR review, PR/main/tag
CI, exact merge-commit wheel verification, annotated tag, non-draft GitHub
Release, single asset, and anonymous digest-matching download remain mandatory.
Beta validation remains external human/client evidence after publication.
