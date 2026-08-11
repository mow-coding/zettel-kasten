# Letter 129 project-update collision remediation gap

Date: 2026-08-12 KST

## User correction and intent

The user reported that recent public releases still left beta clients unable to
update and instructed the development work to begin immediately. The correction
is important: detecting a collision without providing a usable official
recovery route is not a completed update experience.

## Protected-source boundary

Only the one explicitly named Letter 129 feedback artifact was read. The
protected archive, project source mirror, canonical records, credentials, and
other feedback artifacts remain untouched. This development record does not
copy private paths, entry names, source bytes, or private digests.

## Reported v0.3.315 incident

- A verified public v0.3.315 runtime was used against a v0.3.313 project.
- `project-version-update --dry-run` correctly stopped with 25 opaque
  `ignored_or_untracked_runtime_source_shadow` collision references.
- Inspecting the 25 references one by one took 212.214 seconds.
- Every inspection returned `inspected`, but none exposed a supported
  remediation. The boolean fields appeared false without saying whether the
  entry kind was actually inspected or merely outside the v0.3.315 eligibility
  branch.
- No approved update or preservation was attempted. Project source, pin, and
  version remained v0.3.313, and no update receipt or archive mutation occurred.

## Preliminary development finding

The v0.3.315 preservation service evaluates relocation eligibility only for an
exact target-file overlap that is an ignored, index-untracked, regular,
single-link, bounded file. A runtime-source-shadow reference does not enter that
branch, so its kind and Git eligibility remain unevaluated while the public
booleans look like verified negative facts. The service also recomputes the
complete materialization plan once per entry and has no one-plan batch
inspection surface.

## Implementation loop

1. Reproduce runtime-shadow files and directories in disposable Windows Git
   projects.
2. Add content-free entry-kind and evaluation-state truth.
3. Inspect all bounded opaque references from one immutable plan instead of
   rescanning once per reference.
4. Route each supported kind to an official preview-first remediation. Preserve
   user-owned bytes; derived-bytecode cleanup must remain explicit and
   approval-gated.
5. Return a fixed `remediation_unavailable` blocker and safe next action for
   unsupported, reparse, special, ambiguous, or over-bound entries.
6. Prove the complete sequence: blocked update preview, official remediation,
   fresh preview, separate approved update, aligned source/pin/version/receipt.
7. Run independent review, broad regression, package/release checks, and public
   install verification before asking beta clients to retry.

## Implemented correction

- `project-version-update-collision --action inspect-all` now derives and
  classifies the complete digest-bound conflict set in one planner pass.
- Runtime-shadow results distinguish regular files, plain directories,
  reparse/special/unsupported entries, derived `.pyc/.pyo`, and plain
  `__pycache__` directories without exposing private names or paths.
- The bytecode route opens only when the complete, untruncated private set is
  ignored, index-untracked, real, bounded, single-link derived bytecode/cache
  state. Mixed or ambiguous sets have no automatic remediation.
- Repair-plan authority is bound to the exact release target, materialization
  digest, Git HEAD/ref snapshot, and private file/directory set. Counts alone
  do not authorize deletion.
- Repair approval uses the same project version-update lock, revalidates the
  complete binding under that owned lock, records a private intent, removes
  only the exact opened file identity, verifies empty cache-directory removal,
  and writes a create-only completion receipt.
- Late hardlinks, same-name/same-byte replacement files, directory-removal
  failure, post-delete durability failure, receipt failure, unsafe junctioned
  receipt roots, over-bound inventory, and partial recovery all stop with
  explicit blocked/partial/recovery truth rather than a false success.
- A mounted archive root resolves to the owning parent project so the same
  root accepted by the updater also works for the official repair flow.
- Multi-collision operation guidance now gives one batch inspection followed
  by three separate manual phases: bound repair plan, reviewed repair
  approval, and a fresh update preview. It never retries the old update
  approval automatically.

## Verification so far

- The exact 24 bytecode files plus one cache directory fixture reproduces 25
  update conflicts, repairs the exact set, reaches a fresh zero-conflict
  preview, and completes a separately approved update.
- The actual CLI route, not only the service API, completes batch inspect,
  bound repair plan, approved repair, and fresh update preview without private
  entry-name disclosure.
- Letter 129 focused integration and existing completion-workflow regressions
  are green. Independent product and release reviews completed with no
  remaining P0, P1, or P2 finding.

No merge, tag, public wheel, or beta-client live acceptance claim is made at
this checkpoint.

## Release-track records and focused evidence

The v0.3.316 source and packaging track updated package/root version truth;
`CHANGELOG.md`; `VERSIONING.md`; English/Korean README, upgrade, and install
guides; capability, canonical-entrypoint, version-truth, command-routing, and
public-documentation maps; the runtime Skill and update/operator references;
the public Letter 129 decision log; and the v0.3.316 release note.

The historical v0.3.315 public release note and Letter 127/128 decision records
remain byte-exact. A v0.3.316 regression test fixes their SHA-256 values and
verifies that only the current v0.3.316 release note is packaged.

Focused release evidence completed in this worktree:

- v0.3.316 release-doc tests: 6 passed;
- historical v0.3.315 release-doc tests: 6 passed;
- package-resource tests: 7 passed;
- root source-checkout shim: 1 passed;
- predecessor-surface tests: 9 passed;
- capability/documentation tests: 152 passed;
- private resource/index tests: 11 passed, 2 skipped;
- installed-wheel tests: 37 passed;
- source-fidelity documentation tests: 7 passed;
- release-readiness tests: 5 passed;
- resource synchronization check: 145 files synchronized for v0.3.316;
- public link, Korean language, public privacy, and Runtime Skill release gates:
  all passed.

These are implemented-source and local-test facts. Merge, external CI, exact
tag, GitHub Release, public wheel, fresh installation, real-project update,
beta-client success, and human acceptance remain separate evidence states.

## Final local verification before publication

The frozen candidate completed the following separate verification runs. Some
tests intentionally overlap across the focused, compatibility, and full-suite
runs, so the counts are recorded per run rather than summed into one invented
unique total.

- Letter 129 core, CLI, repair, and operation-control: 50/50 passed.
- Existing completion and v0.3.315 collision compatibility: 121/121 passed.
- All non-CLI unittest modules: 1,485 tests passed with 27 environment skips.
- The complete monolithic CLI suite: 1,375 tests passed with 8 environment
  skips.
- CI's seven pytest-native modules: 210/210 passed.
- Independent release/package/contract audit: 226/226 passed, with version,
  EN/KO command parity, historical-byte preservation, package-resource, and
  privacy checks all clean.
- An offline fresh-wheel smoke test built and installed
  `wom_kit-0.3.316-py3-none-any.whl`, verified all 145 packaged resources, both
  CLI entry points, both MCP entry points, Runtime Skill lifecycle, onboarding,
  and strict doctor checks.

The full CLI and non-CLI runs recorded unchanged source/test/Git fingerprints
from start to finish. The final implementation audit reported no remaining
release-blocking or non-blocking finding. This still does not claim a commit,
remote CI, merge, tag, GitHub Release, public wheel, beta-client execution, or
human acceptance; those evidence layers begin only after publication steps
actually complete.

## First remote-CI portability correction

Draft PR #62 started the repository's full Ubuntu and Windows matrix. The first
candidate exposed test-environment mistakes, not a product-runtime failure:

- one Windows shard could not create the test's intentionally injected Git
  commit because the cloned temporary mirror had no repository-local test
  author identity and the clean runner had no global fallback; and
- two Ubuntu shards calculated historical-document hashes from LF checkout
  bytes while the original constants had been captured from a Windows CRLF
  worktree.

The fixture now assigns its fixed non-personal test name and email inside the
temporary mirror. The historical-source test now hashes canonical Git text
after CRLF-to-LF normalization and uses the canonical LF hashes. No product
implementation, historical source document, or public contract changed.

The exact formerly failing test passed with global Git configuration
intentionally unavailable. Under that same condition, the complete Letter 129
focused set passed 50/50 and the 28 existing project-update tests passed 28/28.
The six v0.3.316 release-document tests also passed on Windows with the
cross-platform hash rule. A new remote CI run remains required before merge or
release.
