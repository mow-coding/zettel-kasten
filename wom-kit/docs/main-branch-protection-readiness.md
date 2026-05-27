# Main Branch Protection Readiness

Status: public operations baseline
Version: v0.2.54

GitHub may warn that the `main` branch is not protected. That warning is a safety recommendation, not proof that the repository is broken.

In plain language: branch protection is a GitHub setting that can prevent risky changes to important branches. It can stop force pushes, prevent branch deletion, and later require checks or reviews before a change is merged into `main`.

v0.2.54 does not enable branch protection yet. It documents a staged path toward it.

## Current State

v0.2.53 introduced a local release-readiness gate:

```powershell
python wom-kit\tools\check_release_readiness.py
```

That gate currently runs:

- public link hygiene,
- Korean product-language hygiene,
- public privacy hygiene.

This is local verification only. It is not CI yet. It is not branch protection yet. It does not change GitHub repository settings.

## Recommended Staged Path

The safer path is gradual:

1. Stage 0: keep the current local release-readiness gate.
2. Stage 1: protect `main` from force pushes.
3. Stage 2: protect `main` from branch deletion.
4. Stage 3: add GitHub Actions that run the release-readiness gate.
5. Stage 4: require that status check before merging into `main`.
6. Stage 5: optionally require PR review or release-supervisor review before merge.

This lets the project tighten safety without suddenly blocking the existing release flow.

## Why Not Enable Everything Immediately

The current release-supervisor workflow still depends on local verification and direct release authority.

Strong branch protection can be helpful, but turning it on too early can also interrupt a working release process. Required status checks should exist before GitHub requires them. GitHub Actions should be introduced and tested in a separate future batch before they become mandatory.

The practical order is:

```text
local release gate
-> optional CI workflow
-> required status check
-> stricter branch protection
```

## Safety Boundary

v0.2.54 is documentation and version bookkeeping only.

This release does not:

- call GitHub APIs,
- add GitHub Actions,
- enable branch protection,
- change repository settings,
- change product CLI behavior,
- change product MCP behavior,
- change archive service behavior.

It also does not add ZET transport, provider sync, trust/import/apply behavior, attestation/signature writes, projection writes, recommendation behavior, workers, payments, consensus, blockchain behavior, or full-auto behavior.

## Future Bridge

The local release-readiness gate can later become:

- a GitHub Actions workflow,
- a required status check,
- part of a stricter branch-protection policy.

Those steps should be separate, explicit releases so the project can verify each layer before making it mandatory.
