# v0.3.288 Public Release Verification

Date: 2026-07-30

## Exact Source Identity

- local `main`: `41440e6949d4b4a9a84a0a62744f5f90dfafe649`
- `origin/main`: `41440e6949d4b4a9a84a0a62744f5f90dfafe649`
- annotated tag object: `a57de577a06b459feccd400804134d4a0b4af60f`
- tag target: `41440e6949d4b4a9a84a0a62744f5f90dfafe649`

The tag was not moved or recreated.

## Test And CI Gates

- exact-SHA main workflow `30517031159`: success
- tag workflow `30522776332`, attempt 2: success
- Windows tag job: 1,777 tests passed
- Linux Python 3.10 and 3.12 jobs: success
- release readiness and packaged-resource synchronization: success
- exact merged-source local Windows suite: 1,777 passed, 19
  environment-dependent skips, 0 failures in 855.231 seconds

The first tag attempt reached the old 45-minute Windows job budget while
tests were still progressing. It ended with cancellation/KeyboardInterrupt,
not an assertion failure. The clean retry passed in 41 minutes 44 seconds, so
the release used no exception.

## Published Release

- release:
  `https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.288`
- asset:
  `wom_kit-0.3.288-py3-none-any.whl`
- size: 1,205,955 bytes
- SHA-256:
  `29136dbbce5e877db80d24917b0936b14913e30497dc1b996eb1ed9b9c5ae473`
- draft: false
- prerelease: false

The GitHub asset digest exactly matched the reviewed local wheel.

## Anonymous Public Lifecycle

The wheel was downloaded through the public release URL without `gh`
authentication into a new temporary directory. Its SHA-256 matched the value
above. It was then installed into a fresh Python 3.12 virtual environment,
including its declared PyYAML dependency.

Verified installed evidence:

- distribution version: `0.3.288`
- `archive version --format json`: version `0.3.288`, exit 0
- console entrypoints:
  `archive`, `archive-mcp`, `wom`, `wom-mcp`

No beta archive command was run and no beta archive file was changed.
