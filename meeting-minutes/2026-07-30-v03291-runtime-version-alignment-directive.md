# v0.3.291 runtime version alignment directive

Date: 2026-07-30

## Why this release exists

Beta letter 104 exposed a real three-layer version split:

- the beta project's installed-version pin and source mirror are v0.3.286;
- the `archive.exe` found on `PATH` imports an editable development checkout;
- that imported checkout reports v0.3.282.

The existing `archive version` command diagnoses this mismatch, while
`project-version-update` intentionally changes only the project source mirror,
pin, and receipt. WOM has no provenance-aware global Python installer
lifecycle, and runtime Skill install/uninstall manages AI guidance rather than
the Python CLI.

This release must close the immediate usability gap without pretending that a
project update replaced the global executable.

## Release boundary

This release MUST:

- Extend the read-only `archive version <root>` result with a bounded
  `runtime_alignment` object and deterministic `next_safe_actions`.
- Distinguish at least:
  - no project inspected;
  - running CLI aligned with a self-consistent project source mirror;
  - project source/pin must be repaired or updated before use;
  - a self-consistent project source mirror differs from the running import
    and is safe to invoke as a project-scoped bridge.
- Keep default output path-redacted. It may expose logical project-relative
  locations, version labels, fixed status/reason codes, and safe command
  descriptions, but not absolute paths, exception text, environment contents,
  credentials, or private archive data.
- Under the existing explicit `--no-redact-local-paths` opt-in, return a
  structured exact argv for the verified project-scoped bridge:

  ```text
  [current sys.executable,
   "-I",
   <absolute verified source mirror>/wom-kit/cli/archive.py,
   "version",
   <absolute inspection root>,
   "--format",
   "json"]
  ```

- Emit that argv only when the source mirror package version,
  `pyproject.toml` version, and project pin are mutually consistent and the
  wrapper file exists within the verified mirror.
- Treat "verified mirror" as a local Git integrity claim, not merely matching
  version strings. Require real non-symlink/reparse project paths, the exact
  mirror Git worktree root, a clean checkout except its allowed untracked
  `installed-version.txt`, an untracked pin, the complete runtime Python
  source set tracked at `HEAD`, no unsafe index flags, index/`HEAD` agreement,
  exact raw worktree bytes for those sources, and a closed source tree without
  importable extras, bytecode caches, native extensions, or unsafe path
  components. Require an exact annotated `v<source-version>` tag at `HEAD`,
  all three tagged source version files in agreement, and local evidence that
  the tag is reachable from `origin/main`. Check only whether the fixed origin
  configuration key exists; never read the URL value and never contact the
  network.
- Require the wrapper to repeat the closed-tree and raw-byte checks
  immediately before import, force the selected source root ahead of any
  environment path, reject preloaded external `wom_kit`, and verify the
  imported package and CLI module locations before dispatch.
- Describe the bridge truthfully: it runs the selected project source for one
  invocation; it does not replace `archive` on `PATH`, mutate the Python
  environment, infer pip/uv/editable provenance, or restart an already
  imported process.
- Render the new status and safe actions in text mode without weakening JSON
  stability or changing the command's existing mismatch exit code.
- Correct the shipped runtime Skill update instructions so they point to the
  real `wom-kit/cli/archive.py` wrapper and include the parser-required
  `--target` argument for `project-version-update`.
- Keep Python CLI lifecycle and runtime AI Skill lifecycle explicitly
  separated in public documentation.

This release MUST NOT:

- Run pip, uv, pipx, git fetch, or any installer/update command.
- Add or claim a global CLI self-update, uninstall, or repair mechanism.
- Guess how the active Python command was installed.
- modify the beta tester archive or execute WOM commands inside it.
- write project files, pins, source mirrors, receipts, shell profiles, PATH,
  Python environments, or runtime Skill installations.
- expose an absolute bridge argv in default redacted output.

## Required regression evidence

At minimum, tests must prove:

1. Default JSON and text remain path-redacted, including when the running
   import and project mirror differ.
2. A mutually consistent mirror and pin that differ from the running import
   produce a stable bridge-available status.
3. Explicit `--no-redact-local-paths` returns the exact structured argv using
   `sys.executable`, `-I`, the actual `wom-kit/cli/archive.py`, and the
   inspected root.
4. A missing wrapper, malformed/missing version metadata, or source/pin
   disagreement fails closed and never returns an executable bridge argv.
5. A dirty, non-Git, symlinked/reparse, untagged, lightweight-tagged,
   wrong-HEAD, wrong-version, untracked-wrapper, missing-origin, or
   origin-main-unreachable mirror fails closed and never returns a bridge
   argv.
6. An already aligned and integrity-verified project reports alignment without
   a replacement claim.
7. The result explicitly states that global `PATH`/Python installation and
   runtime Skill installation were not changed.
8. Existing `archive version`, project-version-update, redaction, runtime
   Skill, documentation, packaged-resource, and release-readiness tests remain
   green.
9. The corrected runtime Skill examples use the real wrapper and a non-empty
   `--target` placeholder.
10. Hidden index flags, index divergence, raw-byte mismatch, ignored
    bytecode, shadow source, native extensions, hostile `PYTHONPATH`, preloaded
    external modules, and import-location mismatch all fail closed.
11. The origin probe passes only the fixed configuration key name and neither
    reads nor exposes a credential-bearing URL value.

## Parallel ownership

- Production owner:
  - `wom-kit/src/wom_kit/archive_services.py`
  - `wom-kit/src/wom_kit/archive_cli.py`
- Regression-test owner:
  - `wom-kit/tests/test_cli.py`
- Supervisor:
  - public/runtime-Skill documentation;
  - capability matrix and documentation tests;
  - version, changelog, release note, decision log, resource sync;
  - integration review, full-suite verification, rebase, commit, and release.

No owner may commit, push, tag, publish, modify another owner's files, or touch
the beta archive.

## Release order

This local checkpoint is stacked on the local v0.3.290 candidate so work can
continue while earlier CI runs. It may not be published until every
predecessor has been released and this candidate has been rebased onto the
exact public v0.3.290 commit:

```text
v0.3.287 -> v0.3.288 -> v0.3.289 -> v0.3.290 -> v0.3.291
```
