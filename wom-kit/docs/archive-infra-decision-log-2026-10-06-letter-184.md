# Archive infra decision log: letter 184 (2026-10-06)

Status: part 1 implemented for v0.4.65 under the owner's standing instruction
("읽고 작업 시작해"). Part 2 (session-owned proof for zettel-objet link
changes) follows in the next release (sequential small releases,
2026-09-24). Executing AI: Claude Fable 5.1. The design choices below were
made by the worker's recommendation under the owner's 2026-09-25 design
delegation; they were not individually approved.

Letter 184 came from v0.4.64. In one conversation the helper completed 21
objet registrations and 43 zettel-objet links without approval windows (the
session-ref problem of letter 183 is solved). A session-scoped
`git-backup-reconcile-plan --dry-run` then answered `ok: true`,
`session_output_selection_classified`, `selected_output_count: 2`. A repeated
preview stayed in `git_receipt_provenance` for more than ten minutes and was
interrupted after about 634 seconds.

## What the two selected outputs are, and why not more

A session-scoped backup selects a changed file only when an authenticated
record proves that the whole file is that session's output. Three producers
exist: the session's own decision receipts, source-intake outputs (receipt,
prepared capture request, completion receipt) and whole documents of a
session local recovery. The customer's two outputs are of the second kind.

Objet registration (`objet_capture_batch`) and `zettel_objet_link` have no
such producer. Their Git-managed changes are the changed zettels, new link
and capture receipts and rows of the objet ledger. The preview left them
uninspected and unselected without saying so. That silence is the defect of
this letter; the first preview's selection itself was correct.

The objet ledger (`objects/manifests/files.jsonl`) is one file shared by
every conversation. The operator guidance already states that shared archive
files are left out of a session-scoped backup by design and are backed up by
the archive-wide `git-backup-plan` after the person agrees to include every
activity's pending changes. That decision stands.

## Decisions for v0.4.65

1. A CLI preview carries `session_backup_coverage`, content-free:
   - the selected outputs by kind;
   - the roles of every Git-changed path, as fixed labels derived from
     product directory names (never a path);
   - this session's own succeeded approvals by operation, read from the
     MAC-verified claim store by their session mark, each labelled
     `session_ownership_provable`, `no_git_managed_output` or
     `not_provable_as_session_owned_yet`;
   - the shared-by-design roles and the official archive-wide route;
   - that objet bytes are never in a Git backup, with the commands that
     report their remote preservation and readability;
   - plain sentences for the person.
2. An approval given through a window carries no session mark. It is counted
   as unmarked and attributed to no session.
3. If the claim store cannot be listed completely, the block says
   `unavailable`; it is never read as "no operations". The preview itself
   does not fail for that.
4. The block is computed for previews only. The approved write path is
   unchanged and does not list claims.
5. The MCP projection keeps its closed field list and does not carry the
   block.

## The long second preview

Not reproduced at the customer's scale, and its cause is not established.
Found by reading the code: one fresh preview authenticated every
source-intake original and every local-recovery control of the whole archive
twice (once to discover candidate paths, once to select), and neither stage
reported a count.

1. The `git_output_scope_discovery` and `git_receipt_provenance` progress
   lines carry `current` and `total`: authenticated originals and receipt
   candidates checked so far.
2. Inside one fresh preview or write the selection stage reuses the
   discovery stage's authenticated inventory after re-checking that the
   context inventories (or control candidates) are unchanged. Write-time
   revalidation of every selected proof against the approval claim is
   unchanged.
3. `long_run_guidance` in the preview states that a preview is read-only,
   that interrupting it has no effects, that there is nothing to resume, and
   that a count which has not advanced for five minutes is the point to
   interrupt and report the last progress line.

## Part 2 (next release)

Session-owned proof for the per-file outputs of `zettel_objet_link`: the
changed zettel (HEAD holds the approved preimage, the worktree the result of
exactly this session's links) and the link receipts. The evidence pattern
already used for session-scoped object storage (a receipt that names an
approval whose MAC-verified claim carries the session mark and the same
context digest) is the starting point. The objet ledger stays archive-wide.

## Boundaries

Verified with a real temporary Git repository, registry and claims, and
synthetic files. The customer's archive, the cause of the 634-second preview
and the effect of the reuse on their timings are not verified.
