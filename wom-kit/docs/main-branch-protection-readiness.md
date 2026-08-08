# Main Branch Protection Readiness

Status: active `main-required-ci` ruleset with historical staged-rollout record
Current checkpoint: v0.3.307
Original baseline: v0.2.54

GitHub may warn when a default branch is not protected. That warning is a
safety recommendation, not proof that the repository is broken.

In plain language: branch protection is a GitHub setting that can prevent risky changes to important branches. It can stop force pushes, prevent branch deletion, and later require checks or reviews before a change is merged into `main`.

v0.2.54 did not enable branch protection. It documented the staged path that
the repository later completed through the active v0.3.302 remote ruleset.

## Current State

The local release-readiness gate runs:

```powershell
python wom-kit\tools\check_release_readiness.py
```

- public link hygiene,
- Korean product-language hygiene,
- public privacy hygiene,
- runtime Skill package validation.

The same gate and the complete supported-platform test matrix run in GitHub
Actions. Pull requests are aggregated by one stable `Required CI` status check.

The remote ruleset is named `main-required-ci`; its enforcement is active for
the default branch. It requires a pull request and `Required CI`, blocks branch
deletion, and blocks non-fast-forward updates. The ruleset is a GitHub
repository setting, not product behavior inside WOM-kit.

## Staged Path And Current Result

The rollout used this gradual path:

1. Stage 0: establish the local release-readiness gate. Complete.
2. Stage 1: protect `main` from non-fast-forward updates. Complete.
3. Stage 2: protect `main` from branch deletion. Complete.
4. Stage 3: run release readiness and tests in GitHub Actions. Complete.
5. Stage 4: require the stable status check before merging. Complete through
   `Required CI` and the active `main-required-ci` ruleset.
6. Stage 5: optionally require a second human approval. Not enabled in the
   single-owner workflow; pull-request use is still required.

### CI And Enforcement Status

Stage 3 shipped in v0.3.260 as `.github/workflows/ci.yml`. It runs the
release-readiness gate, packaged resource synchronization, and the complete
WOM-kit suite on `ubuntu-latest` (3.12 and the supported 3.10 floor) and
`windows-latest` (3.12).

After the workflow produced stable evidence, v0.3.302 completed the remote
enforcement step. The `main-required-ci` ruleset now requires `Required CI`
for pull requests and blocks branch deletion and non-fast-forward updates.
Remote enforcement must still be verified from GitHub before a current-state
claim; a Markdown file cannot prove that a repository setting remains active.

Its first runs justified the staging order: they surfaced two cross-platform
defects that the Windows-only development machine could not observe, and
because the check was not yet required, fixing them did not block the release
flow.

That staged observation allowed the repository to make CI required only after
the cross-platform workflow had demonstrated a stable check name and behavior.

## Why The Rollout Was Gradual

Required status checks needed to exist and run successfully before GitHub could
safely require them. The first optional CI runs found cross-platform defects
that the Windows-only development machine could not expose. Those defects were
fixed before enforcement became active.

The practical order is:

```text
local release gate
-> observed CI workflow
-> stable Required CI check
-> active main-required-ci enforcement
```

## Safety Boundary

The original v0.2.54 change was documentation and version bookkeeping only.
This current-state update also changes no GitHub setting by itself.

This release does not:

- call GitHub APIs,
- add GitHub Actions,
- enable branch protection,
- change repository settings,
- change product CLI behavior,
- change product MCP behavior,
- change archive service behavior.

It also does not add ZET transport, provider sync, trust/import/apply behavior, attestation/signature writes, projection writes, recommendation behavior, workers, payments, consensus, blockchain behavior, or full-auto behavior.

## Current Operational Rule

Treat a pull request as merge-ready only after the stable `Required CI` check
passes. Before claiming that `main` is currently protected, verify that the
remote `main-required-ci` ruleset still has active enforcement for pull
requests, branch deletion, non-fast-forward updates, and the required status
check. Documentation and cached local refs are not proof of current GitHub
settings.
