# Archive Infra Decision Log - v0.3.273 Title Remap Revert Plan

Date: 2026-07-28

Status: accepted for implementation

## Context

Letter 101 asks for an approved way to undo a completed title-remap write.
v0.3.269 solved the earlier evidence gap by preserving complete prior canonical
bytes and recording their content-addressed descriptors in each immutable
receipt. v0.3.270 through v0.3.272 separately solved diagnosis, planning, and
execution for interrupted uncommitted writes.

A completed receipt is different: it marks a committed human-reviewed change.
Reverting it must preserve that history and must not overwrite any later
canonical edit.

## Decision

1. Add CLI-only read-only `zet-title-remap-revert-plan`, alias
   `title-remap-revert-plan`; expose no MCP method.
2. Select one immutable completed receipt by archive-relative path and exact
   externally reviewed receipt SHA-256. Never echo the private path.
3. Require the complete bounded title evidence audit to be healthy, complete,
   and clean. Retained transaction journals or a common lock must be resolved
   before planning a completed compensation.
4. Revalidate every current participant against the receipt's applied
   whole-file, title, and body hashes.
5. Revalidate every prior-byte object and manifest record, parse it privately,
   and prove that replacing only its title with the current private title
   recreates the current whole file exactly.
6. Bind the source receipt, its original write evidence, the audit digest,
   every applied-to-prior transition, and the deterministic future revert
   receipt location into one plan digest.
7. Keep title text/hash/length, body text, zet id/path, proposal SHA, reviewer,
   evidence paths, provider values, secrets, and absolute paths out of output.
8. Write and delete nothing. A later approval-gated writer remains a separate
   release boundary.

## Standards Cross-Check

Git documents `revert` as recording new commits that reverse changes introduced
by existing commits. The existing commit remains part of history.

Microsoft's compensating-transaction pattern requires enough stored
information to undo an operation, warns that a blind restore can overwrite
concurrent changes, recommends idempotent compensation steps, and requires
end-to-end correlation and audit.

WOM adopts the narrow relevant rule: preserve the committed source receipt,
revalidate the present state, bind the exact prior-state evidence, and later
record compensation as a separate event.

Primary references:

- https://git-scm.com/docs/git-revert.html
- https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction

## Consequences

An operator can now review a content-free, exact completed-title revert plan
without editing canonical memory. v0.3.273 itself cannot change a title. The
next writer release must repeat this complete validation under the common
title lock, require explicit approval, write crash-recovery evidence before
mutation, restore only the already verified prior bytes, and append a separate
immutable revert receipt.
