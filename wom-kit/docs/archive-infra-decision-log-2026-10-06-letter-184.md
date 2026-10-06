# Archive infra decision log: letter 184 (2026-10-06)

Status: part 1 implemented for v0.4.65 and part 2 (session-owned proof for
zettel-objet link changes) for v0.4.66, under the owner's standing
instruction ("읽고 작업 시작해") and the sequential small releases rule
(2026-09-24). Executing AI: Claude Fable 5.1. The design choices below were
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

## Part 2: this session's zettel-objet links (v0.4.66)

Reproduced through the real CLI in a temporary Git repository: a session
with an `allow_all` grant writes a link without a window; Git then shows the
changed zettel, the new link receipt, the before-snapshot and the
session-object-usage record, and the v0.4.65 preview reports the approval as
outside the selection.

A fifth producer, `session_claimed_zettel_objet_link_output`, selects for
the session that owns the link approvals:

| Output | Git state required |
|---|---|
| changed zettel | modified; HEAD is the recorded preimage; the worktree is exactly this session's links |
| link receipt | new whole file |
| before-snapshot | new whole file whose bytes hash to the recorded preimage |
| session-object-usage record | new whole file |

### What is authenticated, and what is verified by content

1. With the archive receipt key (MAC): the approval claim (succeeded,
   operation `zettel_objet_link`, plan and target-binding digests), the work
   session whose grant it used (the claim's presenter block), and the whole
   bytes of the usage record, which is bound to that claim and names the
   linked objet.
2. The link receipt names the zettel, and its bytes are not MAC-bound (the
   claim binds only a digest of the target, which the receipt cannot
   reproduce). **This is a deliberate, delegated deviation from the rule that
   no unauthenticated record is authorship evidence.** It follows the
   evidence already accepted for session-scoped object storage
   (`object_storage_scope._session_owners`: a receipt that names an approval
   whose verified claim carries the session mark and the same context
   digest), and adds these conditions:
   - the receipt passes the existing schema and path-binding validation;
   - it repeats the claim's context, plan and target-binding digests;
   - it links the objet of the MAC-verified usage record;
   - it is the only receipt that names that approval. Two receipts naming
     one approval prove nothing for either;
   - a rewritten receipt that points at another zettel fails the receipt's
     own path bindings and is ignored.
3. The zettel change is verified by content, not taken from the receipt:
   - Git's HEAD blob must be the preimage the first link recorded; the
     retained before-snapshot is read and hashed against it;
   - the worktree file must be the postimage the last link recorded;
   - every step between them must be an accepted link of this same session
     (a chain; two links from one preimage, a gap or a loop are refused);
   - the parsed difference between preimage and worktree must be nothing but
     the appended asset entries of those links, in order, and `updated_at`.
4. A zettel with any other pending edit, a link of another conversation on
   the same zettel, a link approved through a window (no session mark), or an
   unreadable snapshot stays unselected and uncommitted. Its receipts and
   usage records can still be selected.
5. A link proof is created only for the selected session's own outputs.
   Another session's link outputs are excluded as ownership-unverified.

### Write-time revalidation

The approved Git writer re-audits every original link claim and usage record
with its own claim (`exact_terminal_record_session_ref`), re-reads the
receipts and re-checks the zettel bytes immediately before each Git effect,
as for the other producers. The original-review route revalidates with the
key provider. Scope schema v5 binds the link proofs; v1 to v4 decode byte
for byte as before.

### Not covered

- The objet ledger stays archive-wide by design.
- Objet registration (`objet_capture_batch`): its capture receipts have no
  MAC-bound terminal record and are not selected yet. Planned next.
- Links written before v0.4.34 have no session mark on their claims.

## Boundaries

Part 2 was verified through the real CLI: link writes under a grant, the
preview, the approved Git write with its push to a local bare remote, and
resume; plus a forged and a duplicated receipt, a tampered usage record, a
second conversation, a window-approved link and edits before and after a
link.

Verified with a real temporary Git repository, registry and claims, and
synthetic files. The customer's archive, the cause of the 634-second preview
and the effect of the reuse on their timings are not verified.
