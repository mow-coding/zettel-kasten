# Decision Log: v0.4.19 Pinned Native Runtime Import

Date: 2026-09-05

Status: revised correction implemented and locally verified; final candidate
CI, installed public workflow and release remain pending.

## Context

The real installed runtime failed before approval because the selected Unicode
extension's absolute path exceeded the ordinary Windows native-loader limit.
An identical binary loaded successfully through the equivalent extended-length
path. Source tests and the other CI jobs passing did not prove installation.

## Decision

- Keep the metadata normalization helper's exact prior bytes, fingerprint,
  package pins and generated index SQL. A path-loading correction does not
  justify migrating an existing index or redefining the normalization contract.
- Install a lazy, dependency-specific finder from package initialization and
  the source-checkout shim. Initialization does not import the native engine
  or archive services. Lightweight version inspection must remain available
  even when that dependency cannot load.
- This is an explicit revision of the earlier no-import-hook decision:
  `sys.meta_path` gains one process-local finder immediately before the existing
  exact `PathFinder`. Do not change `sys.path`, computer PATH, DLL search flags,
  launcher bytes, runtime identity/supply checks, Windows settings or project
  locations. An absent/replaced `PathFinder` is not permission to invent one.
- Only a long Windows `unicodedata2` extension selected by that `PathFinder`
  may receive an equivalent absolute extended-length path, verified as the same
  file. Unrelated names are ignored. A short-path or custom-loader specification
  already selected by `PathFinder` is returned unchanged, not looked up twice.
  Recheck adjacency when called: a finder subsequently inserted between the
  pair must keep its newly selected precedence.
- Use Python's documented finder/spec protocol. The normal import machinery
  owns locks, initialization, cache publication and failed-import cleanup;
  remove the manual private `_load`/`_ModuleLockManager` dependency. Never
  publish a partial module or replace an existing cached module manually.
- A missing or broken pinned dependency is a failure, not permission to switch
  credential normalization to another Unicode database.
- Preserve strict, content-free installed failure evidence, separately from
  successful full-journey evidence. Diagnostic-only modes cannot pass the
  release gate. No previous candidate result substitutes for final candidate CI.

## Consequences

The finder changes process-local import behavior for one dependency, not the
Unicode engine or its normalization. If normalization changes later, its
fingerprint and schema must be versioned honestly; this compatibility approach
cannot hide a semantic change behind historical pins.

Known bounded compatibility limit: when the first path lookup misses, the
original `PathFinder` can run once more before later meta finders. A stable
standard filesystem miss remains a miss, and later fallback is preserved. A
stateful custom path-entry finder returning different answers on consecutive
calls can behave differently. Do not claim universal custom-finder equivalence.
Replacing the interpreter's `PathFinder` or suppressing later fallback would
broaden this correction and is deliberately not done.

The fix addresses the reproduced dependency import, not every possible long
Windows path operation. Native long-path, custom-finder precedence, import
concurrency/failure cleanup, existing index reopening and the actual installed
public workflow need verification. No client data processing or release
completion is claimed here.

References: [Python meta-path protocol](https://docs.python.org/3.12/reference/import.html#the-meta-path)
and [finder/spec interfaces](https://docs.python.org/3.12/library/importlib.html#importlib.abc.MetaPathFinder).

Detailed sequence and source references are in the
[reassessment minutes](../../meeting-minutes/2026-09-05-recovery-train-reassessment.md).
