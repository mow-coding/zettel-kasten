# v0.3.295 Private Objet Metadata And Safe-Label Implementation

Date: 2026-08-01

Status: implementation and source verification complete; publication in
progress

## User Intent

Continue the accumulated beta-feedback work in small, independently reviewed
releases. This batch must make a remembered private source name representable
without changing SHA-256 identity or exposing private names through ordinary
public, CLI, MCP, or search surfaces. The user asked the release train to
resume from durable local evidence after desktop-task interruptions and to
publish each release only after it is ready.

## Authority And Boundary

The implementation follows Letter 105, its intake and release-train decision,
the exact v0.3.294 public predecessor evidence, and the independently cleared
v0.3.295 implementation directive.

This release is deliberately contract-only:

- two closed Draft 2020-12 public schemas;
- one pure in-memory normalization, validation, projection, and ambiguity
  reference module;
- pinned Unicode 17 normalization and derived case-fold/whitespace/bidi data;
- exact predecessor surface regression; and
- documentation and package-resource synchronization.

It adds no metadata writer, recovery action, index ingestion, private finder,
database migration, CLI command, MCP tool, provider call, external scan, or
object-byte access. Those remain separate later releases. The beta archive and
beta letters are read-only authority inputs; no beta archive content is
modified by this batch.

## Implementation Chronology

1. Confirmed the exact public v0.3.294 merge predecessor
   `845588144c713b585e67985bc93a0f341e6fe53c` and its public wheel evidence.
2. Rechecked the v0.3.295 directive byte identity and independent
   implementation-authority clearance.
3. Created the dedicated branch
   `codex/v0.3.295-private-objet-metadata-contract` from that exact
   predecessor.
4. Preserved official Unicode 17 `CaseFolding.txt`, `PropList.txt`, and
   `NormalizationTest.txt` fixtures with fixed LF bytes and SHA-256 evidence.
5. Added a deterministic generator and committed immutable Unicode tables.
   Runtime code reads neither those fixtures nor the network.
6. Added exact v0.3.294 CLI, MCP input-schema, database-source, and
   package-resource surface baselines. The new release must preserve all
   non-resource surfaces and make only the authorized resource delta.
7. Added the two schemas and pure reference module with content-free failure
   wrappers, strict bounds, deterministic ambiguity handling, and a
   structurally generic-only public projection.
8. Added `unicodedata2==17.0.1` as the pinned runtime Unicode engine and
   `jsonschema[format-nongpl]==4.26.0` as a CI/test-only standards oracle.
9. Updated checked-layer rediscovery wording while keeping the private
   metadata layer non-complete and unable to support a global absence claim.
10. Updated public contract, decision, release, upgrade, install, capability,
    security, and release-train records. A preflight audit caught and corrected
    one stale statement that still described CI as PyYAML-only.
11. Synchronized the exact 105-file package-resource set and reran the broad
    documentation, rediscovery, runtime-guidance, hardening, Unicode,
    predecessor-surface, and wheel-checker group: 261 passed and 4
    environment-specific cases skipped.
12. Independent contract review found three fail-closed gaps that the initial
    focused suite had not exercised: recursive traversal of a deeply nested
    serialized projection, a Unicode-data-version mismatch that could return a
    normal blocked-name result before the version gate, and recursive equality
    on cyclic non-JSON reason values. The implementation now uses iterative
    cycle-safe traversal, gates every normalizer branch before derivation or
    ordinary blocked results, and compares only the contract's bounded scalar
    uniqueness forms.
13. The interrupted first full-suite pass also exposed a stale
    `philosophy-implementation-evidence` status line. Both English and Korean
    documents now name v0.3.295, and that ten-test documentation module passes.
14. One auxiliary read-only review task was stopped by an automated platform
    classification before it could return a final report. Its already
    reproduced local findings were preserved and fixed; a fresh, ordinary
    contract-conformance review is required instead of treating the interrupted
    task as evidence.
15. Expanded the private contract/schema suite from 41 to 59 tests with every
    required closed-object, boundary, candidate/evidence combination,
    public-nonreflection, deep/cyclic input, Unicode mismatch, and
    runtime-to-Draft direction required by the authority. Together with the 10
    Unicode tests, the focused contract group is 69/69 green.
16. A fresh independent contract-conformance review reported P0 0, P1 0,
    production P2 0, and CLEAR. Its additional 300,000 generated JSON-shaped
    helper calls produced no raw exception. A separate staged public
    provenance/privacy review also reported P0/P1/P2 0 and CLEAR.
17. The first complete 2,006-test source pass reached every test but ended with
    one Windows temporary-directory cleanup error after the detached-stdio
    descendant check. The application assertion had exposed a real launch
    race: a fast virtual-environment launcher could create its interpreter
    child between `Popen` and later Job Object assignment.
18. The installed-entrypoint verifier now creates the Windows process
    suspended, assigns the kill-on-close Job Object before the first
    instruction, resumes the one main thread through Toolhelp APIs, and
    explicitly terminates, waits for, and closes the job. The detached-child
    regression passed 50 consecutive fresh fixtures; the complete wheel-check
    test module passed 37/37. An independent containment review reported
    P0/P1/P2 0 and CLEAR, with 100 normal cleanup iterations, 50 immediate
    child-race iterations, and 25 timeout iterations all clean.
19. The next complete source-suite attempt reached all 2,008 tests but was not
    accepted: one runtime-alignment success-path subprocess exceeded that
    test's 30-second outer timeout under full-suite load. The exact result was
    2,008 run, 22 skipped, one error, and exit 1. The failed stderr evidence has
    SHA-256
    `ad41415c1177effdfe6fa5ae46ac447e8d7a8fa29c71b946119c1f74514a0078`.
20. Standalone reproduction passed, and an independent read-only audit measured
    the exact successful bridge at 24.635, 24.793, and 23.515 seconds in three
    fresh fixtures. The product bootstrap retains its own fail-closed bounded
    operations; no product behavior has a 30-second aggregate contract. Other
    tests of the same successful bridge already use a 60-second outer bound.
    The audit classified this as a release-candidate test flake, P1 for the
    release gate, with P0 0 and production P2 0.
21. The minimal correction changes only that successful bridge test's outer
    timeout from 30 to 60 seconds. It does not increase a product timeout or
    alter fail-closed behavior. The exact test then passed three serial runs
    (48.371, 51.566, and 48.908 seconds of unittest execution), and the full
    19-test runtime-alignment group passed in 345.909 seconds with two skips.
22. The next fresh complete run used staged tree
    `781629e268e8021a4f6498e6aab58adfa091f9fc` with no unstaged or untracked
    files. It passed all 2,008 tests in 2,587.852 seconds with 22 skips, no
    failure or error, and exit 0. The stderr evidence SHA-256 is
    `22152cb6d105b712aeecc37cb86992043ce8a7d0e94bea5b59e637db67c494d5`;
    stdout was empty with SHA-256
    `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
    and the exit marker SHA-256 is
    `13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354`.
    The evidence-only update to this minute follows that run and must receive
    the short documentation/readiness gates before commit. Clean-wheel evidence
    and the public release chain remain pending at this point in the chronology.

## Agent Provenance Boundary

The observed product context identifies the primary role as an OpenAI Codex
desktop implementation task. The task's system context describes Codex as
based on the GPT-5 family, but it exposes no platform-signed served-backend
attestation or exact deployment identifier. This record therefore preserves
the observed product and role, the available family-level description, and
the evidence boundary without guessing a more specific hidden model.

### Primary Implementation And Release-Supervision Role

- observed product/app: Codex desktop app task environment;
- runtime role: implementation supervisor, integrator, verifier, and release
  operator for this batch;
- exact served model ID or platform attestation: `not_exposed`;
- UI model label observed by this role: `not_observed`;
- inference telemetry or backend routing: `not_exposed`;
- model transition or fallback observed in this task: `not_observed`;
- exact public predecessor:
  `845588144c713b585e67985bc93a0f341e6fe53c`;
- source branch:
  `codex/v0.3.295-private-objet-metadata-contract`;
- human authority: the project owner explicitly authorized continuing the
  staged release train; final scope and beta acceptance remain human
  authority.

### Collaborating Codex Roles

Separate collaboration subtasks in the same desktop project context handled
bounded, non-overlapping work:

- schema, pure-module, and focused-contract implementation;
- Unicode 17 fixture, generator, table, and exhaustive-conformance work;
- exact predecessor surface capture and regression;
- current-version documentation-test synchronization; and
- read-only dependency, documentation, and boundary pre-audit.

For these roles, exact served model IDs, UI labels, telemetry, and platform
attestations were not exposed to the primary task. No transition or fallback
was observed. Contribution and review claims are therefore attributed to
task roles and durable code/test evidence, not to an invented backend model
name.

## Verification Record

Accepted evidence so far:

- official Unicode fixture byte/SHA checks: passed;
- deterministic Unicode table generation check: passed;
- Unicode focused suite: 10 passed;
- expanded private metadata schema/contract focused suite: 59 passed;
- private contract plus Unicode focused group: 69 passed;
- broad documentation, rediscovery, runtime-guidance, security,
  installed-wheel checker, Unicode, and predecessor-surface group: 261 passed,
  4 skipped;
- exact package-resource synchronization: 105 files for v0.3.295;
- deep serialized input, cyclic Python container, and Unicode-version mismatch
  direct probes: fixed content-free results with no raw exception;
- philosophy implementation-evidence documentation module: 10 passed;
- independent contract conformance: P0 0, P1 0, production P2 0, CLEAR, plus
  300,000 generated JSON-shaped calls with no raw exception;
- staged AI-role provenance and public-privacy audit: P0/P1/P2 0, CLEAR;
- first complete source-suite attempt: all 2,006 tests reached, 22 skipped,
  one Windows descendant-cleanup race exposed and therefore not accepted as a
  pass;
- repaired installed-entrypoint/wheel-checker module: 37 passed; detached
  descendant regression: 50 consecutive fresh fixtures passed;
- independent Windows containment review: P0/P1/P2 0, CLEAR; 100 normal
  cleanup iterations, 50 child-race iterations, and 25 timeout iterations
  passed;
- second complete source-suite attempt: all 2,008 tests reached, 22 skipped,
  one runtime-alignment success-path test exceeded its inconsistent 30-second
  outer test timeout, exit 1, and therefore was not accepted;
- independent bridge-timeout audit: release-gate test flake P1, P0 0,
  production P2 0; exact successful bridge measured 24.635, 24.793, and
  23.515 seconds;
- corrected bridge test: three serial passes; complete runtime-alignment group:
  19 passed, 2 skipped, 345.909 seconds;
- accepted complete source suite: 2,008 passed, 22 skipped, no failure/error,
  2,587.852 seconds, exit 0;
- release-readiness gate: 4/4 passed;
- test virtual environment: `pip check` passed with
  `unicodedata2==17.0.1`, Unicode data `17.0.0`, and test-only
  `jsonschema==4.26.0`;
- Python 3.10 Linux binary availability probe for
  `unicodedata2==17.0.1`: passed.

These are source-worktree checks, not public-release evidence. The synchronized
105-resource check and complete source suite are now present. The final record
must still add the clean wheel, installed entrypoints, exact merge commit, CI,
annotated tag, GitHub Release, and anonymous asset redownload before calling
v0.3.295 public.
