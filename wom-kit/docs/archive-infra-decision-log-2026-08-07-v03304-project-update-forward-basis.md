# Decision Log: v0.3.304 Project Update Forward Basis

Date: 2026-08-07
Status: implementation and local release candidate verified; PR and exact-tag gates pending

## Context

Beta Letter 112 section 10 reported that a project pinned and checked out at
v0.3.300 could not update to v0.3.301. The updater called it a downgrade only
because the command was loaded from an unrelated v0.3.302 development
checkout. Its own output already showed the intended pin transition and that
the import origin was outside the project mirror.

The defect remained reproducible with the public v0.3.303 wheel against the
beta-test project: project pin and mirror v0.3.300, target v0.3.301, external
runtime v0.3.303, and one false forward-only blocker.

## Decision

- Define the forward-only comparison set as every exact stable version read
  from recognized project pins and the project-local source mirror.
- Exclude the already loaded runtime from that decision because the
  transaction neither rewrites nor reloads it.
- Keep the running version and import-origin relation in structured output.
- Warn when an external runtime is newer than a target that is still forward
  relative to all recognized project state.
- Keep fail-closed blocking when the target is lower than any recognized
  project pin or source version.
- Expose the comparison basis and runtime non-authority in the result, and give
  a specific recovery instruction for true downgrade blockers.

## Consequences

Developers and beta testers may run a newer global or development WOM-kit
while safely updating an older project through released tags. The updater no
longer confuses process context with project state. It still cannot downgrade
the files it controls, and every existing approval, origin, integrity,
quiescence, receipt, rollback, and restart boundary remains unchanged.

## Verification Plan

- Prove the old behavior with a failing regression before the code change.
- Prove an external newer runtime does not block a forward project update.
- Prove a target below the actual project source and pins remains blocked.
- Re-run the exact Letter 112 dry-run against the beta-test project without
  changing its source mirror or pin.
- Complete focused, full-suite, platform CI, wheel, exact-tag, release-asset,
  and anonymous-install gates before claiming the patch released.

## Verification Evidence

- The new regression failed against the old comparison and passed after the
  change. All 28 updater-focused tests pass, including real downgrade, tag,
  path, lock, interruption, rollback, and external-runtime cases.
- The real beta-test project dry-run now returns `ready_for_approval` for
  v0.3.300 to v0.3.301 with zero blockers, zero files written, and unchanged
  pin bytes, mirror `HEAD`, and mirror status.
- 166 version, documentation, package-resource, predecessor-surface, and root
  shim tests pass. Release readiness passes all four public checks, and the
  packaged resource mirror is synchronized at 144 files.
- A clean v0.3.304 candidate wheel passes 144 resource checks, 176 wheel-file
  checks, all four entrypoints, both 121-tool MCP inventories, runtime Skill,
  onboarding preview/write, and strict Doctor. Candidate SHA-256 is
  `a92b79ef32bf9c96c55903010880fc65a05539198102294dc648cdeda7954fcd`.
- The first PR CI run caught three new occurrences of a private project label
  in this public decision log. The wording was generalized, and the exact
  sealed privacy regression now passes locally before the CI rerun.
- PR platform CI, exact merge-tag rebuild, GitHub Release asset agreement, and
  anonymous public reinstall remain separate release gates.
