# Archive Infra Decision Log - v0.3.269 Approved Title Remap Write

Date: 2026-07-28

Status: accepted, implemented, and locally release-verified

## Context

The v0.3.263 plan deliberately refused to write because title replacement had
an unresolved privacy conflict:

- exact revert needs the old title bytes;
- receipts must not store title text;
- hashes cannot reconstruct missing bytes.

The pilot now has 2,701 reviewed rows ready to apply, so a local script remains
unacceptable. It would bypass exact-current-byte validation, durable prior-byte
preservation, immutable review evidence, runtime rollback, and interruption
evidence.

WOM already resolved the same artifact-primacy problem for ordinary canonical
revision in v0.3.248: store exact complete prior file bytes in the ignored local
content-addressed object store, register them in the local object manifest, and
put only a text-free snapshot descriptor in the receipt.

## Decision

1. Add CLI-only `archive zet-title-remap-write` and alias
   `title-remap-write`. MCP receives no write tool.
2. Require exactly one of `--dry-run` or `--approve`.
3. Bind every run to all of:
   - the private proposal SHA-256;
   - the complete v0.3.268 read-only plan digest;
   - a separate candidate write-plan digest;
   - the exact current bytes of every canonical participant.
4. A new approval also requires a safe `--reviewed-by` actor and
   `--affirm-titles-reviewed`. Neither value grants authority on a dry-run.
5. Replace only the one top-level YAML `title` scalar. Preserve BOM, line
   endings, every other frontmatter value, the body, and `updated_at`.
   Duplicate top-level title keys or an unlocatable scalar block the batch.
6. Before the first canonical mutation:
   - derive one SHA-256 object id from each exact complete prior file;
   - write or verify its bytes under `objects/sha256/` without overwrite;
   - register or verify all missing local object-manifest records in one
     manifest-lock acquisition and one atomic batch append;
   - verify every snapshot and manifest record;
   - publish one private text-free transaction journal.
7. Then atomically replace and verify each canonical file and write one
   immutable private apply receipt last.
8. The receipt and journal may contain private zet ids and archive-relative
   paths, before/after file hashes, before/after title hashes, proposal bases,
   and snapshot descriptors. They contain no old or new title value, body text,
   proposal filename, absolute path, provider URL, token, or secret.
9. CLI output contains no zet id/path, title value/hash/length, proposal path,
   snapshot path, reviewer value, journal path, absolute path, or provider
   value.
10. An ordinary runtime failure restores every attempted canonical file to its
    exact prior bytes, removes a partial receipt, and removes the journal and
    lock only after verified rollback. Verified content-addressed snapshots
    remain for deterministic reuse.
11. A hard process exit may leave before/after canonical states, the journal,
    and the lock. This release does not auto-resume or auto-delete that
    evidence. A separate audit/recovery release must classify it.
12. A valid existing apply receipt plus exact current after hashes makes an
    exact retry a no-write `already_applied`.

## Batch Performance Contract

The object manifest must not be rescanned or rewritten once per title. The
writer acquires its manifest lock once, builds one index, writes/verifies all
content-addressed snapshot objects, atomically appends all missing records in
one rewrite, and performs one final indexed verification.

The existing 5,000-row proposal ceiling and a 256 MiB total canonical-byte
ceiling bound memory and rollback work. Operators may split larger practical
reviews into smaller proposal files without changing the receipt contract.

## Candidate Byte Contract

PyYAML compose-node marks locate the exact top-level title value span in plain,
quoted, literal-block, or folded-block YAML. The replacement is one JSON-quoted
YAML scalar. A block scalar's consumed line ending is restored after the
replacement.

The writer then parses before and after bytes and proves:

- the new parsed title exactly equals the reviewed proposal value;
- all other parsed frontmatter is equal;
- the body is byte-for-byte equal;
- BOM and newline convention are preserved.

This is a mutation verifier, not a general YAML reserializer.

## Receipt And Snapshot Boundary

The prior-byte object is local recovery evidence, not a remote-backup claim and
not a user-visible objet publication. The receipt binds:

- proposal SHA-256;
- plan digest and write-plan digest;
- reviewer and explicit affirmation;
- row order, identity/path, proposal basis;
- exact before/after file hashes;
- exact before/after title hashes;
- one verified content-addressed before-snapshot descriptor per row.

Publishing title hashes in normal CLI output remains forbidden. The receipt is
private archive evidence and stores no title text.

## Deliberate Follow-Up Releases

v0.3.269 does not implement:

- archive-wide title-remap receipt audit;
- automatic or approval-gated retained-journal recovery;
- approved title-remap revert;
- reapply after an approved revert;
- importer fallback that prevents future identifier-shaped titles.

The immutable receipt, exact snapshots, and journal are designed so those
features do not need to invent missing history later.

## Consequences

The pilot can apply reviewed source titles through an auditable WOM command
instead of a one-off local script. A successful result proves exact reviewed
bytes were installed and receipted after prior-byte preservation. It does not
prove source truth, title quality, remote backup, or provider synchronization.
