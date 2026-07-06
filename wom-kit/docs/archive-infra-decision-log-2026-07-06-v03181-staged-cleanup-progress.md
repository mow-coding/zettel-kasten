# Decision Log - v0.3.181 Staged Cleanup Progress

Date: 2026-07-06
Batch: v0.3.181.
Anchor: v0.3.180 public release.

## Problem

The basoon operator reported that `staged-cleanup-check` still had a no-output problem. The
verifier is intentionally report-only and deletion-safe, but on a large staged folder or a very
large source/store hash it could appear stalled until the final report printed.

## Decisions

- **DEC-1 - Add opt-in progress only.** `--progress` streams to stderr; default text/JSON output
  stays unchanged for existing scripts.
- **DEC-2 - Keep progress content-free.** Progress lines include stage names, counts, and
  large-file byte totals only. They do not add staged file names, object ids, local absolute paths,
  provider URLs, credential refs, tokens, or secret values.
- **DEC-3 - Cover the long phases.** Progress spans manifest loading, zettel reference scanning,
  staged tree walking, staged entry verification, and large source/store SHA-256 hashing.
- **DEC-4 - Keep cleanup report-only.** The command still never deletes, moves, uploads, or
  writes cleanup state. The exit contract remains `0` only when the report is `ok` and
  `safe_to_cleanup`.
- **DEC-5 - Keep hash behavior stable.** `sha256_path` gets an optional callback, but the digest
  result and existing callers remain unchanged.

## Consequences

Operators can now rerun:

```bash
archive staged-cleanup-check <archive-root> --staged <folder> --dry-run --progress --format json
```

If the command is slow, the last progress line should identify whether the wait is in manifest
loading, zettel reference scanning, staged walking, verification, source hashing, or store hashing.
