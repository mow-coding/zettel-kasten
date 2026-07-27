# Archive Infra Decision Log - v0.3.264 Durable Canonical Writes

Date: 2026-07-26

Status: accepted for v0.3.264 implementation and release

## Context

The v0.3.257 batch was split because it was too large, and the second half was
never done. It is still sitting in `stash@{0}` as a work-in-progress checkpoint.
The two open items recorded there were:

1. a canonical zet overwritten during a forced shutdown can be left half-written;
2. a batch that edits several abstracts and stops partway records nothing about
   how far it got, so it can be neither resumed nor reverted.

This release closes (1). (2) is untouched and is stated as excluded below.

## What Was Actually Wrong

45 call sites reach disk through `write_text_atomic` / `write_bytes_atomic`,
including the abstract backfill write and the revision apply and revert paths,
i.e. real canonical zet mutation. The two writers were in different states and
this log's first draft got that wrong, so both are stated precisely here.

**`write_text_atomic` had three defects.**

- **No `fsync`.** `write_text` then `replace` lets the rename become durable
  while the data behind it is not. On a power loss the destination can be empty
  or truncated where a complete canonical zet had been.
- **Fixed temp name.** `path.name + ".tmp"` means two concurrent writers to one
  path share one temp file. Reproduced before fixing: the loser's `finally`
  unlinks the winner's temp mid-flight.
- **No parent creation.**

**`write_bytes_atomic` had one, and an earlier draft of this release missed it
entirely by editing a function that does not run.** The module defined
`write_bytes_atomic` **twice**; the later definition shadowed the earlier one, so
the draft's careful rewrite of the earlier one was dead code and all 15
byte-writing call sites — the ones this log named as the flagship examples —
inherited nothing. The live definition already reserved its temp with `O_EXCL`
and already `fsync`ed. What it actually lacked was the retried rename and parent
creation. The dead definition is removed.

**Both lacked a retried rename**, and this was found by measuring rather than by
reading. A unique temp name did **not** fix the concurrent-writer race: with
unique temps in place, `os.replace` still failed in roughly five of six runs,
because Windows `MoveFileEx` refuses to replace a file anyone holds open. The
unique name fixed the *temp* collision; the *destination* was still contended.
The same failure hits a single writer whenever a virus scanner or search indexer
has the zet open.

Separately, `zettel_edge_write` and `zettel_edge_revert` used **no** atomic
writer. They overwrote the canonical zet in place and, on `OSError`, wrote the
original text back — also in place. `restore_zettel_edge_batch_snapshots` and
`create_draft_zettel` had the same shape.

## Decision

1. Fix the writers rather than the call sites. One change to
   `write_text_atomic` / `write_bytes_atomic` gives all 45 call sites durability
   and collision-safety; converting them individually would have been 45 chances
   to miss one.
2. **The change is byte-neutral by construction.** The temp file is opened with
   `encoding="utf-8"` and deliberately **no** `newline` argument, so output —
   including platform newline translation — is identical to what these functions
   have always produced. A regression asserts byte-identity against a plain
   `Path.write_text` for text and against `write_bytes` for raw bytes.
3. **Newline determinism is explicitly out of scope.** `Path.write_text` emits
   CRLF on Windows and LF on POSIX, so canonical bytes already depend on the
   writing platform. That is a known, handled condition, not a discovery:
   `bytes_normalized_for_content_compare` folds BOM and CRLF/CR to LF and is the
   single normalized-equality definition reused by reconcile, the doctor
   format-drift branch, and retire's snapshot tolerance;
   `raw_bytes_drift_is_newline_or_bom_only` distinguishes an autocrlf re-checkout
   from a content edit; and the docstring states the raw sha mismatch is
   *intended* so drift stays visible. Folding a newline decision into a
   durability fix would have made this release a content change that needed its
   own argument. It is separated so this one has no content diff at all.
4. The canonical-mutating call sites route through the atomic writers. The
   existing rollback stays, but it is no longer load-bearing: it only runs on
   `OSError`, never on a process kill, and if interrupted it corrupted the file a
   second time. A partial restore is the worst possible outcome of a rollback,
   which is why `restore_zettel_edge_batch_snapshots` is included.
5. Both writers use the module's existing hidden-dotfile temp convention,
   `.{name}.{random}.tmp`, so a crash leftover is not picked up by an `*.md`
   scan. Interrupted files are left alone rather than swept, since deleting files next to a
   canonical zet on the basis of a name pattern is a bigger decision than this
   release earns.
6. **The rename is retried, bounded, and re-raises.** `fsync` and the retry are
   different guarantees — the first survives a power loss, the second survives a
   lock — and the release needed both. The retry is capped at
   `ATOMIC_REPLACE_ATTEMPTS` with a short linear backoff and re-raises the
   `PermissionError` afterwards, so a destination that is genuinely unwritable
   (read-only file, denied ACL) still fails loudly instead of being masked by a
   spin. Only `PermissionError` is retried; every other error propagates
   immediately.

   This decision exists because the first implementation was verified by
   reasoning and the reasoning was wrong. The unique temp name looked sufficient,
   and the targeted test passed. Running the full suite failed it, and measuring
   showed the destination — not the temp file — was the contended resource. The
   claim was corrected before the release rather than after.

7. **Receipts are made durable in the same release, data and directory entry
   both.** Making the zet durable while the receipt proving it stayed in the page
   cache converts a symmetric loss ("both gone, archive consistent") into an
   asymmetric one ("the archive changed and nothing records why"). A first pass
   fsynced the receipt's data but not its directory entry — and a receipt is
   created with `"x"`, so for a brand-new file the entry is exactly what a power
   cut loses. That inverted the asymmetry instead of removing it, and the review
   caught it.
8. **Only `os.replace` is retried.** The directory flush runs once, after the
   loop. Inside the loop it would re-enter a retry whose temp path no longer
   exists and raise `FileNotFoundError` for a write that in fact succeeded, which
   `zettel_edge_write`'s `except OSError` would answer by rolling a correctly
   written zet back. The loop also has a structural `else: raise` backstop so a
   zero attempt count can never silently perform no rename at all.
9. **The retry budget is deliberately small** (8 attempts, ~0.36 s worst case).
   On Windows a destination held open by an editor or sync client fails
   *persistently*, not transiently, so a batch rollback pays the full budget per
   zet and then still fails. A larger budget would multiply that stall without
   improving the outcome. An aggregate deadline for batch paths is a separate
   change and is named as excluded.

## What This Release Deliberately Excludes

- **The resume record.** Item (2) from the stash is untouched. A multi-zet write
  that stops partway still records nothing about its progress. That needs its own
  design, and it is a prerequisite for any approved write rung in the title remap
  ladder.
- **Newline determinism**, for the reason in decision 3.
- **Sweeping stale `.tmp` files**, for the reason in decision 5.
- **An aggregate retry deadline for batch paths**, for the reason in decision 9.
  A 200-zet rollback against a persistently locked destination stalls for the
  per-write budget times 200 and then still fails partway. Bounding that needs
  progress reporting and a fail-fast that names the holder.
- **Consolidating the two directory-fsync helpers.** `_objet_capture_fsync_dir`
  predates `fsync_directory` and does the same job at seven call sites. Both are
  correct; having two answers to one question is a cleanup, not this release.

## Verification Contract

- Two threads writing one path through `write_text_atomic` produce no errors, the
  final file is exactly one writer's complete output rather than a blend, and no
  temp file is left behind. This fails against the pre-v0.3.264 implementation.
- `write_text_atomic` and `Path.write_text` produce byte-identical files for the
  same text; `write_bytes_atomic` and `write_bytes` likewise for raw bytes.
- Writing to a path whose parent does not exist succeeds and leaves only the
  target file.
- An approved `zettel-edge` write never opens a file under `zettels/` for a
  truncating in-place rewrite, and leaves no temp file behind.

## Consequences

An interrupted canonical write now leaves the previous zet byte-identical rather
than truncated, and that guarantee holds for every path that mutates a zet, not
just the ones someone remembered to convert. The remaining interruption risk is
no longer *within* one file — it is *across* files in a multi-zet batch, which is
exactly the item this release names as excluded.
