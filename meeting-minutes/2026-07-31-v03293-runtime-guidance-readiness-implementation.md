# v0.3.293 Runtime Guidance Readiness Implementation

Date: 2026-07-31

## User Intent

Continue the accumulated beta-feedback release train carefully rather than
claiming that archive guidance is effective merely because files exist. The
release must improve the AI entry route, preserve human approval, and keep
truth boundaries explicit.

## Authority And Scope

The implementation followed Letter 105, the v0.3.293 implementation
directive, and the Letter 105 release-train decision record. This batch is
limited to runtime-guidance readiness and complete operator-feedback routing.
Later v0.3.294-v0.3.299 items remain separate batches.

## Implementation

- Added `wom_kit.runtime_guidance` and the explicit
  `runtime-guidance-readiness` CLI command.
- Bound the explicit invocation to
  `archive runtime-guidance-readiness <archive-root> --host codex --scope repo
  --repo-root <repo-root> --format json`.
- Added real, read-only Codex repository checks for managed runtime Skill
  status and bounded `AGENTS.md` routing anchors.
- Added distinct absent, incomplete, unreadable, unsafe, and unsupported
  diagnostics without echoing paths or source bodies.
- Kept ordinary `runtime-context` and `ai-start-here` at `not_checked` with
  an exact opt-in command and `host_guidance_consumption: not_proven`.
- Advanced action routing to v0.7 and embedded the five-stage
  operator-feedback sequence with a required human gate.
- The sequence names `operator-feedback-plan`, `operator-feedback-ledger`,
  required human review, `operator-feedback-record --dry-run`, and
  `operator-feedback-record --approve --reviewed-by <human-actor>`.
- Any needed Skill change is returned only as
  `runtime-skill-install --dry-run`; no automatic install or `AGENTS.md`
  rewrite is authorized.
- Extended Markdown guidance and the public documentation set.
- Changed no archive content, existing `AGENTS.md`, provider, external
  service, tag, release, or beta archive.

## Verification Record

The new focused runtime-guidance test module contains coverage for a current
Skill plus complete routing, distinct absence diagnostics, unreadable and
unsupported fail-closed behavior, required CLI selectors, no implicit host
inspection, and exact feedback sequencing. Initial focused execution passed
6 tests.

Verified local evidence:

- focused runtime-guidance: 6 passed;
- selected runtime-context, ai-start-here, and feedback CLI regression: 3
  passed;
- capability-document suite: 148 passed;
- packaged resources, runtime Skill lifecycle, and runtime guidance: 36
  passed with 1 environment-permission skip;
- all 27 test modules other than the 3.8 MB `test_cli.py` module completed;
  their initially reported public-hygiene errors were caused by the expected
  staged deletion/addition transition from packaged v0.3.292 to v0.3.293, and
  the four affected modules were rerun after staging and passed as part of a
  200-test verification;
- release readiness passed public links, Korean product language, public
  privacy, and runtime Skill package checks; and
- the clean wheel check passed v0.3.293 with 103/103 resources, 119 wheel
  files, runtime Skill lifecycle, onboarding, strict Doctor, and wheel SHA-256
  `086209755421b971ae4352f30d908cbb9e26fa61ac18347afdf3dcdce01e3d84`.

The complete discovery suite was attempted twice. It exceeded first the
2-minute limit and then the 10-minute limit without returning a terminal
result. No test failure was observed from those timed-out runs, but they are
not counted as a completed full-suite pass. Exact public-predecessor CI/full
verification therefore remains required. A green local subset or clean wheel
is engineering evidence only.

## Independent Review P1 Corrections

The first local commit was independently reviewed before any push or release.
Two P1 issues were found and fixed in one follow-up batch.

1. A hand-edited ownership manifest could place arbitrary text in
   `package_version`. The runtime Skill status projection copied that string
   into `installed_version`, and readiness copied the nested projection. The
   parser now uses the shared exact stable-version policy, invalid values
   become `null`, the state becomes `managed_invalid`, and both JSON and text
   explicitly report `invalid_or_untrusted` without echoing the source value.
2. An existing directory without `archive.yml` passed the directory check and
   later raised while reading `archive_id`. Archive validation now happens
   before host inspection and returns a structured `invalid_archive` blocked
   result. CLI dispatch normalizes expected local inspection failures to the
   same content-free result family.

Regression coverage uses path-like, traversal-like, partial, prerelease, and
sensitive-like version canaries, preserves normal `0.3.293`, checks JSON and
text non-echo, verifies exit 1 for the invalid archive, asserts no traceback or
absolute path, and compares complete test trees before/after to prove no write.

Follow-up verification passed 32 focused runtime-guidance/Skill lifecycle
tests with 1 environment-permission skip, three existing exact-version
redaction tests, 187 resource/document/readiness/Skill tests with the same
single skip, and all four release-readiness checks. The post-correction clean
wheel contains 120 files, verifies 103/103 packaged resources and 333,089
resource bytes, passes runtime Skill lifecycle, onboarding, and strict Doctor,
and has SHA-256
`9fe60140054a5035eb111fc4b11a9b4b81b9b509c2cbdbe8db5657fc1c2226f1`.
This supersedes the pre-review candidate wheel for any later local comparison;
it is still not public-artifact evidence.

## Release Boundary

v0.3.292 is currently a local candidate lineage, not a proven public
predecessor for this branch. Before v0.3.293 is release-ready, rebase onto the
exact public v0.3.292 predecessor and rerun the full suite plus clean-wheel and
public-artifact verification. No push, PR, tag, GitHub Release, anonymous
download, or beta validation is performed in this batch.
