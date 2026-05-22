# Phase 4 Implementation Plan: Archive Lineage + Trust Baseline

Date: 2026-05-21

## Summary

Phase 4 implements the first local baseline for archive lineage and trust gates.

Implemented now:

- `archive-identity.yml`
- archive identity schema validation
- scope vocabulary documentation
- lineage/trust specs
- `archive share --dry-run`
- MCP `share_check`
- workpack package scope/trust metadata
- trust-gated import dry-run
- owner/operator identity metadata
- ownership-transfer planning for child, family, and company archives

Still intentionally dry-run:

- real share
- real merge
- real fork
- real business exit/spin-out
- real ownership transfer
- signed workpacks and signed receipts

## Safety Model

Every future share/merge/fork/import should pass:

```text
scope gate
trust gate
ownership gate when ownership changes
human approval
receipt
```

Phase 4 implements the first two as dry-run checks.

Ownership transfer remains plan-only for Phase 4. The model now records enough structure to plan it safely:

```text
owner
  Person, family, company, or group that owns the archive.

operator
  Person or role that can write, curate, approve, or request transfer.

subject
  Person the archive records are about, such as a child.
```

Example:

```text
child archive while young
  owner: family:household
  operators: person:father, person:mother
  subject: person:child

child archive after transfer
  owner: person:child
  operators: person:child, optional trusted helpers
  receipt: transfer_archive_ownership
```

## Verification

Expected checks:

```text
doctor --strict passes for fake-life-archive
unit tests pass
share dry-run verifies trusted fingerprint
share dry-run blocks missing/mismatched fingerprint
share dry-run excludes sensitive categories by default
MCP exposes share_check but no real share/merge/fork tool
archive-identity.yml records ownership and operators
```

Actual result:

```text
fake-life-archive doctor strict: 0 errors, 0 warnings
unit tests: 55 passed
schema JSON parse checks: passed
py_compile checks: passed
```
