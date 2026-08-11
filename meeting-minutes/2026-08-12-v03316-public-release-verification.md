# v0.3.316 Public Release Verification

Date: 2026-08-12

## Purpose

This closeout records the evidence that became available only after the Letter
129 implementation and local verification were complete. The implementation
history, failure analysis, and pre-publication test evidence remain in
`meeting-minutes/2026-08-12-letter129-update-collision-remediation-gap.md`.

Letter 129 showed that v0.3.315 correctly stopped an update when it found 25
runtime-cache collisions, but did not provide a practical supported recovery
route. v0.3.316 adds one complete batch inspection, a separately reviewed and
authority-bound cache repair, a mandatory fresh update preview, and a separate
update approval. Unsupported or mixed entries still stop without automatic
cleanup.

## Remote CI and merge evidence

- Pull request: https://github.com/mow-coding/zettel-kasten/pull/62
- Final candidate commit:
  `3373cf7fcb380528a2a3ea4a3827da99206af823`
- Final CI run:
  https://github.com/mow-coding/zettel-kasten/actions/runs/31538838599
- CI result: release readiness, four Ubuntu shards, four Windows shards, and
  the required aggregate check all completed successfully; 10 checks succeeded
  and none failed or remained running.
- Merge time: 2026-08-12 07:17:28 KST.
- Merge commit: `2ccc805e3282de8d4f659a7fce2b932e6f9f6dd2`.
- The local `main` branch and `origin/main` were both verified at that merge
  commit with a clean worktree before packaging.

The first CI attempt had exposed two portable-test-fixture mistakes: a clean
Windows runner lacked Git author identity for an intentionally injected test
commit, and Linux used LF checkout bytes while the original historical-document
hash constants had been captured from a CRLF worktree. The follow-up commit set
a fixed repository-local test identity and used canonical LF hashes. No product
runtime behavior or historical source document changed in that correction.

## Tag, release, and public artifact evidence

- Annotated tag: `v0.3.316`.
- The tag resolves to merge commit
  `2ccc805e3282de8d4f659a7fce2b932e6f9f6dd2`.
- Public GitHub Release:
  https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.316
- Published wheel: `wom_kit-0.3.316-py3-none-any.whl`.
- Wheel size: 1,816,242 bytes.
- Wheel SHA-256:
  `34d5bdd2ba9c43f1ec0037bcba91f5df66985c51be96b1cddf6c840251676209`.
- GitHub's asset digest, the merged-main build digest, and the anonymously
  downloaded public-file digest were identical.

The wheel was rebuilt from the merged `main` commit with package-index access
disabled. A fresh installation verified package version 0.3.316, all 145
packaged resources, both CLI entry points, both MCP entry points and their 121
tool inventory, Runtime Skill lifecycle, onboarding, and strict doctor checks.

The published wheel was then downloaded from its public release URL without a
GitHub-authenticated client. A new isolated Python environment installed that
downloaded file successfully, and both `archive version --format json` and
`wom version --format json` reported 0.3.316. The installed distribution and
imported module versions also both reported 0.3.316.

## Evidence boundary and next action

This record proves implementation, local regression, independent review,
remote CI, merge, tag, public release, anonymous download, and fresh
installation. It does not claim that a beta client's affected project has
already completed its update. That final product evidence requires the beta
tester to install v0.3.316 and repeat the documented preview, batch inspection,
repair, fresh preview, and separate approval sequence on the affected project.

No protected archive was opened or modified during publication or public-wheel
verification. No automatic cleanup, automatic update retry, or private entry
name disclosure was introduced.
