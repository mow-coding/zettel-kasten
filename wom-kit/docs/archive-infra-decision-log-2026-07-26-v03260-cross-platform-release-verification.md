# Archive Infra Decision Log - v0.3.260 Cross-Platform Release Verification

Date: 2026-07-26

Status: accepted for v0.3.260 implementation and release

## Context

Release verification for this project has been entirely local and
self-attested. An independent audit labelled that evidence gap
`NOT-VERIFIABLE`: no repository artifact bound test execution to a release
commit, so every "the full suite passed" claim reduced to author attestation.

The project had already written down the remedy. `main-branch-protection-readiness.md`
records a six-stage path whose Stage 3 is "add GitHub Actions that run the
release-readiness gate", explicitly ahead of Stage 4's required status check,
and states that Actions "should be introduced and tested in a separate future
batch before they become mandatory".

The maintainer's development machine is Windows-only. The project's own
documented container runtime is Linux. Nothing had ever executed the suite or
the gate on Linux.

## Decision

1. v0.3.260 implements Stage 3 only: one workflow that runs the existing
   four-checker readiness gate, packaged resource synchronization, and the
   complete WOM-kit suite. It changes no repository setting and is not a
   required status check. Stages 1, 2, 4, and 5 alter GitHub configuration and
   remain separate, explicitly approved steps.
2. The workflow installs only PyYAML. The suite is stdlib `unittest` with
   `subTest`; pytest is declared nowhere and is not introduced as a dependency.
3. Coverage is `ubuntu-latest` on 3.12 and on the 3.10 `requires-python` floor,
   plus `windows-latest` on 3.12 to keep parity with the machine releases are
   cut on. `fail-fast` is disabled so one platform cannot mask the other.
4. The workflow additionally asserts a clean working tree after the suite, so a
   test that writes into the repository fails loudly instead of drifting.
5. Defects the workflow finds are fixed in this same batch when they are
   defects in verification itself, rather than deferred behind a gate that is
   known to be red.

## Findings The First Runs Produced

1. **Packaged manifest was not reproducible.** `iter_source_rows` sorted `Path`
   objects. pathlib compares Windows paths case-insensitively and POSIX paths
   case-sensitively, so `templates/ai-runtime/wom-archive/SKILL.md` ordered
   before `references/` on Linux and after it on Windows. The committed
   manifest was therefore Windows-only and `--check` failed on ubuntu with
   `resource manifest does not match source resources`. The gate could not run
   in the project's documented Linux runtime. Sorting on the source-relative
   POSIX string orders identically everywhere; the regenerated manifest holds
   the same 91 entries with identical `bytes` and `sha256` values.
2. **Traversal detection was platform-flavoured.** `load_prompt_boundary_report_file`
   tested `Path(path).parts` for `..`. On POSIX a backslash is an ordinary
   filename character, so `..\report.json` became a single part, passed the
   guard, and surfaced a raw `ENOENT` instead of the fixed traversal message.
   Nothing escapes the archive on Linux, but a Windows-authored path must not
   change verdict when the archive is opened elsewhere. The sibling
   `resolve_command_result_output_path` already normalized separators before
   the identical check; this path now matches it and also catches nested forms
   such as `a\..\b.json`.
3. **One test hardcoded a separator.** A project-intake assertion required
   `endswith("archive-objets\\intake")`. `recommended_paths` are OS-native
   local paths the human types, so the assertion now compares path components.
4. **One test encoded a console fold position.** The Windows leg alone then
   failed: PowerShell's error formatter hard-wraps `Write-Error` at the console
   width and breaks mid-word, so the developer console produced `daem on` while
   the runner produced `not \nreachable`. The assertion's regex had encoded the
   first of those. Comparing with all whitespace stripped removes the console
   dependency, verified against simulated mid-word folds at every width from 20
   to 120.

The first two are corrections to verification and safety plumbing, not to
product behavior a user depends on. The last two are test defects, and they
failed on opposite platforms — which is the concrete argument for keeping both
in the matrix rather than adding Linux alone.

## Verification Contract

- The manifest regression asserts each group stays ordered by its packaged
  POSIX string, and a separate test pins the sorting mechanism against a
  mixed-case fixture. Both fail against the pre-fix manifest and pass after it.
- Traversal normalization is verified to reject `..\x` and `a\..\b` on every
  platform while leaving ordinary relative paths accepted.
- The complete suite, the four hygiene checkers, and packaged resource
  synchronization pass locally before publication.
- All matrix legs must be green before the release commit is tagged.

## Consequences

Release claims become independently checkable: a run on the release commit
either exists and is green, or it does not. Linux execution is now routine
rather than hypothetical, which matters because the suite's skips are
capability probes — symlink and POSIX-shell cases that never execute on the
maintainer's machine run for the first time on ubuntu.

This batch deliberately does not require the status check, enable branch
protection, add a wheel build to CI (that tool needs network for build
isolation and belongs in a release-only job), strengthen wheel-manifest byte
binding, change MCP error sanitation, or reopen the quarantined
mutation-engine research checkpoint. Those remain separately scoped.
