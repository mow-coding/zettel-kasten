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
