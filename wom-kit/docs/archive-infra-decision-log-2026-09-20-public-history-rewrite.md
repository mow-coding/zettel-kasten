# Archive infrastructure decision log — 2026-09-20, public history rewrite

Executing model: Claude Opus 5, solo and sequential, on the user's explicit
2026-09-19 approval. Full record:
[minutes](../../meeting-minutes/2026-09-20-public-history-rewrite.md).

## Decisions

1. **Rewrite, do not just stop.** Current files were already clean (the
   readiness gate and release-docs tests enforce it), but a private local
   folder name in reachable history is still a public exposure; the user
   decided it must go. The rewrite substitutes fixed placeholders
   (`<user>`, `<client>`) for the two private strings in every blob and
   message; nothing else in history changes (dates, authorship, graph).
2. **Verify by scanning objects, not by trusting the tool.** A full scan of
   every blob and message field before (884 / 4 matches) and after (0 / 0)
   is the acceptance criterion, together with tree equality for `main`, all
   branch heads and every tag from v0.4.14 on (267 refs identical, 180 older
   tags changed only by the substitution).
3. **Force push only with the ruleset paused.** `main-required-ci` blocks
   non-fast-forward pushes; its enforcement was disabled for one push and
   restored, and the rule list was verified unchanged. This is the only
   repository-settings change of the operation and it is recorded here.
4. **Records keep their pre-rewrite ids.** Release evidence, register entries
   and decision logs written before 2026-09-20 are not edited; the minutes
   carry the before/after mapping for `main` and the four released tags.
   From v0.4.32 on, records name post-rewrite ids.
5. **GitHub-side residue is the user's request.** `refs/pull/*` and cached
   unreachable objects are GitHub's to purge; the user files the support
   request with the prepared text.
6. **Evidence chains verify through a committed map.** The v0.4.12 link-index
   reference (`docs/evidence/v0.4.12-link-index-windows-reference.json`)
   records the commit its measurement came from; that commit object no longer
   exists after the rewrite (its source tree carried one private label in a
   docstring), so the first CI run on the rewritten history failed the
   ancestry check on every fresh Ubuntu clone. Rather than weaken the check,
   `docs/evidence/history-rewrite-2026-09-20-commit-map.json` records, for
   each pre-rewrite commit an evidence file names, the rewritten commit, its
   object digest and the rewritten source-tree oid; the test takes that map
   only when the recorded commit is not an ancestor of the tag, and still
   requires the mapped commit to be an ancestor, its object digest to match,
   and the measured script and reference blobs to be byte-identical.
7. **Guard rail going forward.** The public privacy gate already refuses the
   strings in current files; the release-docs tests now also refuse the
   user's account folder name in the documents they cover. Client feedback
   letters are read from the client's folder and never copied into the
   repository (the standing boundary).
