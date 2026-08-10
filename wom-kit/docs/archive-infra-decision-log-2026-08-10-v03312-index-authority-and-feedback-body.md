# Decision: one fail-closed zettel index authority and a separate feedback-body companion

Date: 2026-08-10

## Context

Letters 120 and 123 expose opposite failures from the same generated index.
Readers trust stale rows and return plausible success, while mint duplicate
planning distrusts the same index by silently falling back to a complete
canonical-body scan. Letter 120 separately shows that feedback lifecycle
metadata does not prove that a useful, private, reproducible feedback body
exists.

## Decision

1. Index-backed zettel readers and mint planning use one current-index check.
   Missing, legacy, incomplete, dirty, unsafe, or live-stat-mismatched evidence
   fails closed with a rebuild-required outcome. It never enables a silent live
   body fallback.
2. A current index stores bounded duplicate keys and normalized publication
   fields. Mint checks only indexed candidates, and structured readers can
   select canonical WOM-native results by publication time without guessing
   from filenames or filesystem modification time.
3. Supported mint and retirement mutations update the generated zettel index or
   leave it explicitly dirty. A failed index closeout is not reduced to a
   warning-success result.
4. Mint progress is optional, content-free, flushed to stderr, and keeps stdout
   reserved for the final command result.
5. Feedback body composition remains a companion to the existing lifecycle
   record rather than expanding metadata readers to expose body content. A
   private ignored-local request is digest-planned, explicitly approved,
   written create-only, checked for the required factual and request sections,
   and linked to the lifecycle record by a SHA-256 feedback ref.

## Consequences

- SQLite makes the changes inside one database transaction atomic, but that
  guarantee does not extend across the separate Markdown and receipt files.
  The lifecycle therefore uses an explicit dirty intent and honest
  reconciliation boundary instead of claiming one cross-filesystem commit.
  See the official [SQLite transaction](https://www.sqlite.org/lang_transaction.html)
  and [atomic commit](https://sqlite.org/atomiccommit.html) documentation.
- JSON progress is UTF-8 JSON Lines: every emitted line is one complete JSON
  value and stdout remains the final result channel. See the
  [JSON Lines format](https://jsonlines.org/).
- Existing pre-v0.3.312 indexes require one explicit rebuild before protected
  query or mint use. WOM does not migrate them by silently scanning the archive.
- When a filesystem write fails but every file created by that attempt is
  removed with exact identity and digest evidence, the unchanged index may
  return from dirty to current only after a fresh same-generation live-tree
  proof. Any cleanup or proof ambiguity leaves it dirty.
- Ordinary external or manual changes that alter a path, size, or nanosecond
  mtime are detected by the bounded live stat snapshot. This body-free gate is
  not a content hash: an unmanaged same-size rewrite that preserves mtime can
  evade it, so operators must rebuild after tools that preserve those values.
- A feedback body may exist before its lifecycle record is bound. Body check
  reports that state as incomplete rather than claiming a ready feedback item.
- An ignored-local request is rejected when Git already tracks the exact file.
  `.gitignore` is not treated as retroactive privacy authority for indexed
  content.
- Approved path owners must remain quiescent during create/link cleanup. Static
  symlink and reparse parents are rejected, but portable pathname operations do
  not claim immunity from a hostile same-user directory-swap race.
- Letter 121 source-fidelity work remains a separate next release because it
  governs source-to-draft preservation, not generated-index or operator-feedback
  authority.

Implementation chronology and reproduction evidence are recorded in
`meeting-minutes/2026-08-10-v03312-letter120-121-123-triage-and-index-lifecycle.md`.
