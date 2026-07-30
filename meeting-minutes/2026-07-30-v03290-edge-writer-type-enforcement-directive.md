# v0.3.290 edge writer registry type enforcement directive

Date: 2026-07-30

## Why this release exists

The generic `zettel-edge` writer currently verifies that an edge type ID is
active and that both endpoints resolve, but it does not enforce the active
`types.yml` declaration of which entity types may appear in `from` and `to`.
For example, the active `continues` contract is `Zettel -> Zettel`, yet a
manifested `OriginalObject` can currently reach the write path as its target.

This is a write-safety defect. The fix belongs before any later work that might
activate or expand sequence semantics.

## Release boundary

This release MUST:

- Treat the writer source entity as `Zettel`.
- Map a resolved zettel target to `Zettel`.
- Map a resolved objet target to `OriginalObject`.
- Load the selected active link-type definition from the authoritative
  archive-local `zettel-kasten/types.yml` when present, otherwise from the
  packaged kit registry.
- Require the selected definition to have non-empty lists of safe entity-type
  strings in both `from` and `to`.
- Fail closed before either the zettel or receipt is written when the registry
  contract is malformed, the source entity type is disallowed, or the resolved
  target entity type is disallowed.
- Apply the same rule to `zettel-edge-batch` through its existing delegation to
  the single-edge writer. A disallowed item must never become an approved
  write.
- Return stable, content-free machine-readable contract facts and blockers;
  never echo private target content, paths, registry values, exception text, or
  unresolved user input in a new error field.
- Preserve currently valid manual behavior, including both permitted
  `format_variant` targets and the existing manual-only batch policy.

This release MUST NOT:

- Activate, infer, or redefine `sequence`.
- Change any edge vocabulary definition.
- Add an AI/provider/Notion/MCP write route.
- Mutate the beta tester archive.
- Add migration behavior for already-written invalid edges.
- Broaden batch auto-write policy.

## Required regression evidence

At minimum, tests must prove:

1. `continues` with an `OriginalObject` target is blocked in dry-run and approve
   modes, with no zettel mutation and no edge receipt.
2. `embed` with a zettel target is blocked in dry-run and approve modes.
3. `format_variant` still accepts both zettel and manifested objet targets in
   the manual single-edge writer.
4. Missing, malformed, or empty `from`/`to` contracts fail closed.
5. An archive-local registry remains authoritative; packaged fallback is used
   only when the archive-local file is absent.
6. Batch dry-run/approve cannot write a type-incompatible item and reports its
   policy/result state deterministically.
7. New error/contract fields contain no target content, private filename,
   absolute path, or exception echo.
8. Existing focused edge, batch, format-variant, documentation, resource-sync,
   and release-readiness checks stay green.

## Parallel ownership

- Production owner: only
  `wom-kit/src/wom_kit/archive_services.py`.
- Test owner: only `wom-kit/tests/test_cli.py`, unless a narrowly scoped new
  test module is demonstrably cleaner.
- Supervisor: version metadata, public documentation, release note, decision
  log, meeting minutes, resource synchronization, integration, full-suite
  verification, commit/rebase, and release judgment.

No owner may commit, push, tag, publish, modify another owner's file, or touch
the beta archive.

## Release order

The local checkpoint may be completed while v0.3.287 CI runs, but it may not be
published out of order. The final release chain is:

```text
v0.3.287 -> v0.3.288 -> v0.3.289 -> v0.3.290
```

Every candidate must be rebased onto the exact public predecessor, rerun the
required verification, and produce a clean wheel before tag/release.
