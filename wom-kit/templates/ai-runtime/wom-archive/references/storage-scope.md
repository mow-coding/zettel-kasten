# Object-storage scope and interruption

- For object-storage upload, restore and offload, default to this session's
  capture scope. A missing session or missing attribution is not permission to
  select the archive. Use `--captured-by-session` for an explicitly delegated
  session, `--object-list` for an exact delegated set (including multiple sessions),
  or `--all-sessions` only when the user delegates the whole archive. Never treat
  `--local-bytes-only` or `--max-objects` as a session selector. Check the scope
  and excluded counts before applying the matching plan.
- For a stopped partial upload that must not continue, inspect the original
  plan with `--abandon-started-upload --dry-run`, its exact resume identifiers
  and reviewer; then use the matching `--approve`. Keep existing effects and
  receipts. Start a fresh scoped plan afterwards; do not claim remote success
  or rollback from abandonment. Generic claim finalize is not this procedure.

## Classify before upload

The helper AI owns classification when the user delegates cleanup. Inspect
contents, how files were produced, references and recovery needs. Do not ask
the user to label every file and do not upload the whole working folder first.
Use the private `activity-cleanup` request to record each role and its reason:

- Preserve originals, useful deliverables and recovery evidence.
- Discard proven disposable caches, intermediates and redundant temporary
  copies without intake or upload: `role: temporary`, `disposition: discard`,
  `discard_intent: true`. Record reproducible inputs/steps, verified retained
  copies including alternate streams, or the user's delegated disposal intent.
- Retain uncertain or still-used files: `disposition: retain`. No upload or
  deletion; explain the remaining uncertainty without calling cleanup complete.

A filename, age or ignore rule alone is not disposal evidence. Preserve unique
work, secret configuration, Git history and other activities' dependencies.
Temporary files cannot silently use `preserve`; meaningful intermediate
evidence needs the appropriate role and reason. A valid full-access grant
covers the official child operations without additional approval windows.
Do not delete already-uploaded remote temporary objects through local cleanup.
