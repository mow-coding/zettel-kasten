# Long Operations And Updates

Load this reference for `index`, `index-health`, `project-version-update`,
timeouts, and recovery.

- Use the project launcher `.zettel-kasten\bin\archive.cmd`; a different
  `archive` on PATH is not the project's runtime.
- Run approvals in the foreground. Never background or kill them; after one
  failed `--resume`, read `recovery-plan` and stop.

- Use fresh `--output` for `index` and `index-health`; new updater work may
  choose one automatically. Preserve `operation_ref`.
- After timeout, do not start a duplicate writer. Use exact-root
  `operation-control --action status --dry-run`, bounded `wait`, or
  `recovery-plan`; deadlines are neutral.
- Cancel and resume are unsupported in generic `operation-control`.
  Identifier-free `project-version-update --resume` alone reuses pending bound
  output without `--output`; redisplay may repeat and consumed is history.
  Fresh dry-run and approval share one cleanup preflight. Exact history returns
  `project_version_update_terminal_cleanup_required`: pause same-project writers
  and run identifier-free `--resume`. WOM compacts exact preapproval-abort
  history, and a superseded completed original
  (`terminal_transaction_cleanup_completed`), into proof with no domain write,
  success claim, or fresh authority. Proof-only needs approval.
  `project_version_update_terminal_cleanup_outcome_unknown`
  means stop; never edit locks, pins, transactions, tombstones, or proofs.
- Approved project-update mutation, same-version repair, and mutation-bearing
  resume are Windows-only. On POSIX use preview or read-only inspection; every
  mutation path must fail closed without writing.
- No MCP control, daemon, queue, background launcher, force kill, lock deletion,
  or automatic rollback exists.
- Preview updates. During Windows approval, pause other Git writers and require
  reviewer plus `--affirm-external-writers-quiescent`. After completion, a new
  process must prove `archive version` agreement; this does not prove remote
  release freshness.
- If an updater returns bound collisions, keep the exact target and plan
  digest. Use CLI-only `project-version-update-collision --action inspect-all`
  once for the complete opaque set. Only an exact all-supported cache set may
  continue to a separately reviewed, target/digest-bound
  `project-bytecode-repair`; single eligible payloads retain the separate
  preserve-relocate route. Neither route retries the updater. After success run
  a fresh updater preview and separate approval. Retain uncertain cases and
  locks; never guess a path, delete evidence, or blindly replay.

