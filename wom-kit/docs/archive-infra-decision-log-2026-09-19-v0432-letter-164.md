# Archive infrastructure decision log — 2026-09-19, v0.4.32 (beta letter 164, first half)

Executing model: Claude Opus 5 (implementation, tests, docs, bump, release),
solo and sequential, under the user's standing approval to work through the
backlog without re-asking. Beta letter 164 (2026-09-19) was read from the
client's read-only feedback folder; no client archive, runtime, workspace or
ledger was read or changed. Every fixture below is synthetic.

## Triage of letter 164

The letter lists nine findings and ten requests. They split by what each
needs:

- **v0.4.32 (this release)** — the four items that are bounded read-side
  changes with a clear fixed-vocabulary answer: ② the finalize receipt
  scanner, ⑤ the update snapshot's probe failure kinds, ⑥ the local Git
  backup gap on session-start and evidence results, ⑦ the permission-mode
  preview.
- **v0.4.33** — ① reopening `object-storage-upload` under the v0.4 exact
  approval contract, with ③ (`writer_unavailable` first, `--local-bytes-only`,
  `--progress`, byte-external exclusion before the manifest compare) and ④
  (store-ref label validation) as parts of the same design. This is a writer
  that touches a remote provider; it needs a design pass and an adversarial
  review before code, not a patch.
- **v0.4.34** — ⑧ archival of delivered feedback letters, receipts and
  requests outside the archive with a consistency-check exclusion, and the
  8b same-generation index participation that ⑨ confirms (`mint-zet` /
  `revert-edge` approve results reported `index_marked_dirty: false` and the
  next dry-run was still blocked by `archive_index_rebuild_required`).
- **Answered in the reply, not in code** — ⑨'s materials (three journals,
  the 27-claim list, `idx2.json`) are accepted when the client sends them;
  item 10 (the v0.4.31 batch) is already public.

## Decisions

1. **Finalize scanner streams bytes (②).** `scan_receipt_references` no
   longer parses JSON; every `*.json` regular file under the scan roots is
   read in 1 MiB chunks with a 64-byte overlap and searched for the
   `approval_[0-9a-f]{32}` token. A malformed or large receipt is therefore
   *scanned*, not counted as unreadable. The per-file ceiling moves from
   2 MiB to 256 MiB and the file cap from 50,000 to 500,000; a file above
   the ceiling is `oversize_skipped` (not `unreadable`) and both kinds are
   named by archive-relative path (up to 16 each, `paths_echoed: true` on
   the plan). The scan still fails closed on any incomplete result — the
   letter's "warn instead of block when the oversize file provably names no
   claim" is exactly what the byte scan achieves without a new warning:
   an oversized file that cannot be scanned is the only remaining blocker,
   and at 256 MiB that is not a Doctor receipt.
2. **Probe failure kinds (⑤).** The capped runner records a fixed kind of
   its last failure on a thread-local (`argument_invalid`, `launch_failed`,
   `stream_unavailable`, `timeout`, `output_cap_exceeded`,
   `stream_read_failed`, `stdin_write_failed`); the observation adds
   `probe_budget_exhausted`. The snapshot observation records every probe as
   `{probe, available, return_code, failure_kind}` — the Git subcommand name
   and numbers, never output — and the update preflight, which now reads the
   observation directly, attaches that list as
   `checks.git_transaction_snapshot.detail` when the check is `unavailable`
   or `failed`. The v0419 "second observation is authoritative" test moves
   its fault injection to the observation seam; the fixed check states and
   reason codes are unchanged.
3. **Git backup attention (⑥).** A new content-free block
   (`wom-kit/git-backup-attention/v1`, module `git_backup_attention`) answers
   "what does Git not yet hold?" with counts and whole-day ages only:
   uncommitted change count (untracked / tracked split), last commit age,
   upstream state, ahead/behind counts and the age of the newest commit the
   cached remote-tracking ref knows. It reuses the pinned executable and
   safety flags of `git_backup_plan` (`--no-optional-locks`, no hooks,
   attributes or excludes), runs under one 8-second budget with per-probe
   caps and fails quiet (`state: unavailable` with the probe kinds of
   decision 2; `git_unavailable`; `not_a_repository` with
   `review_recommended: false`). It never touches the network, and the
   backup-evidence GitHub lane keeps `unverified_no_generic_completion_receipt`
   because a cached remote-tracking ref is not proof of the remote — the
   block sits inside that lane as `local_repository_attention` and flips only
   `local_commit_inspected` / `git_repository_inspected` to true. It is
   attached to `ai-start-here` (`git_backup_attention`, summary state and
   count, a warning line and a next step when review is recommended, a
   Markdown section), `backup-evidence` (lane, warning, next action) and the
   `work-session` create / claim envelopes next to `inbox_attention`. No
   path, branch name, remote URL, subject or hash leaves the module
   (`paths_branches_or_messages_echoed: false`, tested with private canaries).
4. **The one-approval commit+push writer is not new code.**
   `git-backup-reconcile-plan --approve` (v0.4.3, letter 139) already
   commits and pushes exact groups behind one native dialog; the friction
   the letter describes is that the client AI must classify every
   `change_ref` in a private selection manifest first. v0.4.33 considers a
   "select every observed change into one group" convenience for the same
   command, bound to the same manifest digest; the reply names the existing
   route now.
5. **Permission-mode preview (⑦).** `work-session --action
   set-permission-mode --dry-run` resolves to the read-only mode
   `permission_mode_preview` (no `--approve` / `--apply` / `--resume` /
   `--review-original`). `preview_permission_mode` shape-checks the refs,
   normalizes the request exactly as the write would, and returns
   `would_set`, the fixed `permission_modes`, `grantable_operations` and
   `always_dialog_operations` lists, or `ok: false` with the refusal code and
   its positional detail; it reads no session state, so ownership is not
   asserted, and it opens no dialog. The next step names the `--approve`
   rerun on the claimed session.

## Questions for the client

- ⑥: whether the archive root is itself the Git repository root or sits
  inside a larger checkout (`repository_scope` reports which); the
  attention counts only the archive subtree either way.
- ⑧: whether "outside the archive" may be a sibling folder the operator
  names, and whether delivered letters should keep their receipts next to
  them or leave a content-free stub in `ops/feedback`.
- ①/③: the exact `object-storage-upload --dry-run` argv that ran the full
  manifest compare before reporting the closed writer, so the v0.4.33
  design starts from the observed order.
