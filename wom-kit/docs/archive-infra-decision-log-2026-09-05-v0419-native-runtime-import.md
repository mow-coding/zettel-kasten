# Decision Log: v0.4.19 Pinned Native Runtime Import

Date: 2026-09-05

Status: accepted correction; final candidate validation and release pending.

## Context

The real installed runtime failed before approval because the selected Unicode
extension's absolute path exceeded the ordinary Windows native-loader limit.
An identical binary loaded successfully through the equivalent extended-length
path. Source tests and the other CI jobs passing did not prove installation.

## Decision

- Correct the two Unicode consumers through one dependency-specific adapter.
  Use only the standard import system's selected `unicodedata2` extension and
  an equivalent absolute extended-length path, verified as the same file.
- Preserve global import paths, DLL search flags, launcher bytes, runtime
  identity/supply checks, Windows settings and project locations.
- Share the original interpreter module lock and loading protocol. Do not
  publish an incompletely initialized module or overwrite an existing one.
  The guarded CPython internal-hook dependency is explicit and must remain
  covered by supported Python 3.10/3.12 CI.
- A missing or broken pinned dependency is a failure, not permission to switch
  credential normalization to another Unicode database.
- Preserve strict, content-free installed failure evidence, separately from
  successful full-journey evidence. Diagnostic-only modes cannot pass the
  release gate. No previous candidate result substitutes for final candidate CI.

## Consequences

The fix addresses the reproduced dependency import, not every possible long
Windows path operation. Native long-path, import concurrency/failure cleanup,
existing normalization contracts and the actual installed public workflow need
verification. No client data processing or release completion is claimed here.

Detailed sequence and source references are in the
[reassessment minutes](../../meeting-minutes/2026-09-05-recovery-train-reassessment.md).
