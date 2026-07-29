# Decision Log: v0.3.281 Activity-Group Membership Write

## Context

Beta Letter 103 showed that an AI could receive an official read route yet
still reach a dead end when the requested archive action needed a real write.
v0.3.280 deliberately stopped at a read-only activity-group plan. That made the
event model reviewable, but it did not let an operator safely apply the reviewed
selection.

## Decision

1. Add one CLI-only approval-gated
   `activity-group-membership-write` membership-add writer.
2. Bind the exact private request hash and the read-only review-plan hash.
3. Rebuild candidates before the lock and again under one archive-local
   exclusive writer lock.
4. Preserve verified before-state snapshots and publish a private transaction
   journal before the first canonical mutation.
5. Atomically change only `frontmatter.facets.activity_group`, leaving anchor
   bytes, bodies, other frontmatter meaning, and `updated_at` unchanged.
6. Publish one immutable receipt only after every final hash verifies.
7. Roll back handled runtime failures immediately.
8. Retain evidence after a hard interruption and add a separate read-only
   recovery plan plus approval-gated recovery executor.
9. Derive recovery from exact before/current/after hashes. Unknown drift enters
   `manual_forensic_hold`; recovery never guesses.
10. Bind the writer-lock state into the recovery plan. Make writer and recovery
    mutually exclusive through the recovery guard plus the same global writer
    lock, including an exclusive recovery claim when a complete journal has
    lost its lock.
11. Keep membership inference and membership removal unimplemented.
12. Expose the implemented writer and recovery commands through AI command-path
    routing v0.4, while continuing to prohibit direct canonical edits.

## Standards basis

- Python's [`tempfile`](https://docs.python.org/3/library/tempfile.html)
  provides same-filesystem temporary files for staged writes.
- Python's [`os.replace`](https://docs.python.org/3/library/os.html#os.replace)
  supplies atomic replacement when source and destination are on the same
  filesystem.
- SQLite's
  [Atomic Commit](https://www.sqlite.org/atomiccommit.html) description informs
  the prepare-before-mutate and classify-from-durable-state transaction model.
  WOM does not claim that multiple Markdown files become one filesystem-level
  atomic unit.

## Consequences

- A reviewed event-member set now has a complete official route from plan to
  approved canonical addition.
- A normal exception returns the set to its exact before bytes; a hard exit
  leaves enough evidence for an explicit, separately reviewed recovery.
- The receipt proves the exact applied set without making private participants
  public in command output.
- An operator must confirm that an interrupted writer is no longer running
  before approving recovery.
- Removal, automatic member discovery, MCP mutation, and general facet editing
  remain separate future decisions.
