# Meeting minutes: v0.3.318 release preparation

Date: 2026-08-13

Status: source implementation and local verification recorded; merge, external
CI, tag, GitHub Release, wheel publication, fresh installation, and physical
host paste acceptance remain separate release or human gates.

## Scope

v0.3.318 responds to protected-archive feedback Letter 131. The source letter
was read without changing the protected archive. No real PAT, Notion account,
reviewed page content, private locator, existing Credential Manager entry, or
protected archive data was used in implementation or verification.

The release scope is limited to:

- honest paste instructions and visible masked-input receipt;
- Ctrl+C-safe cooked console input and cleanup ordering;
- five actionable public intake/provider failure stages;
- strict reason/rollback/absence relationships;
- synthetic automated and opt-in manual acceptance evidence that remains
  clearly separated from real credential enrollment.

## Implemented contract

1. The prompt guides `Ctrl+V`, `Shift+Insert`, Windows Terminal's default
   `Ctrl+Shift+V`, and host-dependent right-click. It keeps the value and length
   hidden and performs no programmatic clipboard read.
2. During the prompt WOM ignores `Ctrl+C`; empty Enter is the documented
   cancellation. Console detach occurs before any default process-terminating
   handler behavior can resume.
3. A complete non-empty line produces only
   `입력값을 받았습니다. 검증 중입니다.` plus the automatic-close sentence
   for a bounded dwell.
4. The public envelopes are `wom-credential-secure-intake-result/v0.2` and
   `wom-credential-workflow-result/v0.2`.
5. The five ordinary reason codes are
   `credential_input_cancelled_or_empty`, `credential_input_not_received`,
   `provider_auth_rejected`, `provider_identity_endpoint_unavailable`, and
   `reviewed_anchor_inaccessible`.
6. Input/cancel outcomes are pre-store with `not_required`. Provider outcomes
   require exact-entry rollback as `deleted` or `delete_failed`; `deleted`
   requires verified absence. Unknown verifier failures stay generic.
7. Mutable input buffers, including temporary UTF-16 duplicates, are wiped.
   Public output excludes secret values, lengths, local paths, native targets,
   reviewed-page ids, provider bodies, and derived keys.

## Local verification received

- Focused secure-intake, visible-console, Notion-adapter, workflow, and CLI
  tests: 104/104 passed.
- Latest visible-console unit selection after the immediate UTF-16 duplicate
  wipe assertion: 7/7 passed.
- Manual host-check tool unit selection: 6/6 passed after exact host-route
  pairing and exact-boolean result validation were added.
- Latest actual Windows API canary: input mode `503 -> 499 -> 503`, code pages
  `949 -> 65001 -> 949`, handler calls `[TRUE]` only, successful
  `FreeConsole`, exact Korean without `???`, echo/VT input off, status dwell,
  no secret reflection, Ctrl+C worker survival followed by empty-Enter cancel,
  and survival/result publication during a forced cleanup-window race.

The actual Windows canary preceded the small immediate-wipe lifetime patch;
the existing final cleanup wipe had already passed, and the new immediate wipe
is covered by the later unit assertion. This distinction is retained instead of
claiming one canary covered code it did not run.

## Manual host acceptance tool

`wom-kit/tools/check_windows_credential_console_host.py` is an opt-in
source-tree check for one human-observed, fixed-synthetic console attempt. It
uses exact matched host-family and launch-route pairs plus bounded gesture labels; separates
`automated_win32_boundary_status` from `actual_host_acceptance_status`; calls no
clipboard API, provider, Credential Manager, or protected-archive data; emits no private
locator; and wipes its mutable synthetic buffer. The visible prompt runs in a
spawned worker so the original terminal stays attached. Only
`(nonempty_bool, exact_bool)` returns to the parent.

No actual physical `Ctrl+V`, `Ctrl+Shift+V`, `Shift+Insert`, or right-click
gesture was performed for this preparation record. The honest status is
`actual_host_acceptance_status: not_performed`. Adding a tool is not the same
as completing its human acceptance exercise.

## Documentation and version work

- Package, source, and repository-shim versions were aligned at `0.3.318`.
- Current README, upgrade, install, status, public-map, capability, runtime, and
  Agent Skill/operator-contract sources were advanced to the new contract.
- New Letter 131 guide, v0.3.318 decision log, release note, and chronological
  minutes were created.
- Historical v0.3.317 release, decision, and meeting-minute records, plus the
  Letter 118-119 guide, were deliberately left unchanged.
- Package resources and runtime mirrors were synchronized after the
  documentation pass. The manifest reports 145 files for v0.3.318, and the
  source/package mirror checks pass byte-for-byte.

## Full-regression feedback loop

The first frozen local regression separated product behavior from release
documentation drift:

- the complete `tests.test_cli` run passed 1,375 tests with 8 environment
  skips and no failures or errors;
- the 88-module non-CLI unittest run executed 1,574 tests with 28 environment
  skips, no errors, and one documentation failure;
- the failure expected `Status: v0.3.318` in the English philosophy evidence
  document, while both English and Korean evidence documents still named the
  v0.3.317 review;
- only those two current-review status lines were advanced to v0.3.318. The
  historical v0.3.252 traceability checkpoint and 2026-08-04 document date
  remained unchanged;
- the focused artifact-primacy and v0.3.318 release-document selection then
  passed 16/16, package-resource synchronization remained clean at 145 files,
  and `git diff --check` passed.

A second full CLI/non-CLI run was briefly launched and intentionally stopped
before producing a result because this chronology itself had to be added to the
candidate record. Those interrupted processes are not release evidence. The
final full regression must start only after this record is present so its
start/end tree is the actual release candidate.

The first PR #66 CI run then found a separate privacy-record issue. Ubuntu
Python 3.10 shard 2/2 reported candidate sealed-surface total 212 against the
unchanged predecessor limit 203. A content-free comparison found exactly nine
new occurrences, all confined to the two new internal minutes and caused by
repeating the protected project's proper name. The predecessor constant,
empty allowlist, and privacy test remain unchanged. The nine references were
rewritten as generic `protected archive` language, after which the exact
privacy subset test and focused release checks must pass before a replacement
PR head is pushed. The failed head is not release evidence.

## Remaining release gates

- run the full repository regression and release-document tests after all
  concurrent edits are complete;
- review the complete diff and confirm historical artifact hashes are unchanged;
- build and inspect the exact wheel in a clean environment;
- merge, external CI, tag, GitHub Release, wheel upload, fresh install, and
  live version verification;
- separately run any desired fixed-synthetic human host acceptance, without a
  real PAT or protected-archive data, and record only bounded result fields.
