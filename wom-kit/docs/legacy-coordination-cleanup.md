# Legacy Coordination Cleanup

Status: exact-root cross-platform dry-run only in v0.4.0; v0.3.307 Windows
cleanup is historical

Current boundary: cleanup approval fails with
`compound_exact_human_approval_binding_required` before workspace read or
mutation. It deletes or creates nothing. Approval examples below document the
historical v0.3.307 receipt-less contract and are not v0.4.0 run instructions.

`archive legacy-coordination-cleanup` previews one retired local-state tree on
every supported platform without writing or exposing content. In v0.4.0 it
cannot remove the tree on any platform. It does not restore MOW Harness
support.

## Beginner Summary

This is not an automatic cleaner.

Think of it as a review-only disposal form:

1. You name one exact workspace root and inspect a dry-run.
2. Stop. Approval returns `compound_exact_human_approval_binding_required`
   before workspace reads or mutation.

The command never searches the computer for old installations. Doctor, upgrade,
project update, archive discovery, and normal artifact-hygiene checks never run
this cleanup. `collab/` is never a cleanup target; its contents are never
traversed or changed by this command.

```text
dry-run found it != safe to delete
old name or old date != safe to delete
approval for one plan != approval for a changed plan
```

## Exact Scope

The positional argument must be an existing absolute workspace-root path. WOM
derives only this one candidate:

```text
<exact-workspace-root>/.mow-harness/
```

It does not accept `.mow-harness/` itself, a relative path, a drive root, an
account-profile root, a UNC/device namespace, or a broader directory to search.
Every supplied ancestor must be a real non-link directory. A sibling `collab/`
remains outside both tree traversal and mutation. Historical v0.3 Windows
handle-retention details below are audit context only.

The command fails closed when the target or any scanned entry is:

- Git-tracked;
- covered by any Git index found at an ancestor of the workspace;
- a nested `.git` entry inside the target, which blocks without being traversed;
- a symbolic link, junction, Windows reparse point, or other special file;
- a Windows named alternate data stream;
- a Linux entry whose `mnt_id` differs from the bound workspace filesystem, or
  another cross-mount entry that cannot be proven safe;
- covered by a caller-supplied Git repository-selection environment override;
- accompanied by an existing cleanup lock or old cleanup tombstone;
- unreadable;
- outside the exact direct-child boundary;
- affected by case drift or an unsafe path component;
- above the reviewed file or byte ceiling; or
- changed between planning, approval, and use.

Unknown state is a blocker, not permission to guess.

## Step 1: Dry-Run

Use the real absolute path to the workspace that you own:

```powershell
$workspaceRoot = 'C:\path\to\one-workspace'

archive legacy-coordination-cleanup $workspaceRoot `
  --dry-run `
  --format json
```

Optional ceilings can make a large or unexpected tree block sooner. `--max-files`
is a conservative scanned-entry ceiling, so directories count toward it too:

```powershell
archive legacy-coordination-cleanup $workspaceRoot `
  --dry-run `
  --max-files 1000 `
  --max-bytes 104857600 `
  --format json
```

The result reports bounded counts, total bytes, fixed state or blocker codes,
and `plan_sha256`. It does not print filenames, file contents, or local absolute
paths. A preview writes and deletes nothing and creates no backup or receipt.
`dry_run_ready` means a reviewable target was found; `target_absent` means there
is nothing to remove; and `blocked` means no approval should proceed. Before
approval, inspect the local directory itself: aggregate output deliberately does
not reveal enough private detail to decide whether every byte is disposable.

Dry-run is cross-platform. On POSIX, a reviewable plan still reports
`approval_platform_supported: false` and `safe_to_cleanup: false`. This does not
mean that the target is malformed; it means v0.3.307 deliberately offers preview
only on that platform.

If you used `--max-files` or `--max-bytes`, use the same values during Windows
approval. They are part of the reviewed plan.

## Platform Boundary

Approved mutation is Windows-only in v0.3.307. Standard POSIX deletion removes a
name, but does not provide a portable atomic operation that means "delete this
name only if it still refers to the exact inode that was reviewed." A retained
file descriptor can prove what was opened, but cannot make a later pathname
unlink conditional on that identity. WOM therefore fails closed: POSIX
`--approve` blocks before creating the cleanup lock and before any mutation.

On Windows, the command keeps the workspace ancestor/root handles open for the
whole transaction. It disposes each exact approved file or empty directory in
place while retaining its verified handle; it does not first rename the tree to
a quarantine name. Windows reparse points and named
alternate data streams block, while Linux dry-run uses `mnt_id` evidence to
block cross-mount entries.

## Historical v0.3 Windows Cleanup Evidence

Historical v0.3.307 Windows runs used the exact unchanged plan digest plus
workspace-owner, external-writer-quiescence, and retired-state-disposal
affirmations. v0.4.0 accepts no approved cleanup invocation and deletes or
creates nothing.

Approval requires all of the following:

- a safe non-secret reviewer id;
- the exact unchanged plan SHA-256;
- explicit workspace-owner authorization;
- explicit confirmation that external writers are quiescent; and
- explicit confirmation that the retired state is disposable.

If `summary.backups_or_receipts_present` is `true`, approval additionally
requires:

```powershell
--affirm-backups-and-receipts-disposable
```

That affirmation means the human reviewed the loss of those recovery or audit
bytes. Their presence is never treated as proof that deletion is safe.

## Result And Interruption Boundary

The command does not create a new backup or cleanup receipt. Creating another
copy of possibly secret-bearing retired state would expand the privacy surface,
and a receipt inside the tree being removed would not be durable evidence.

The command does not rename the target to a new tombstone before deletion. An
old cleanup tombstone left by earlier or interrupted software still blocks a
new operation, but v0.3.307 creates no new tombstone and has no automatic
rollback scheme.

If the first mutation has begun and its outcome is partial or cannot be proven,
the result is conservatively `partial_cleanup_pending`. That is not success. WOM
does not automatically retry, resume, or roll back. Stop other writers and
inspect the local situation; do not loop the apply command automatically. Begin
again with a fresh dry-run only after a human decides how to proceed.

An approved removal is complete only when the result is `cleanup_completed`.

Successful filesystem cleanup removes directory entries in the reviewed tree.
It is not secure media erasure: WOM does not overwrite storage blocks, purge
filesystem journals, remove copies held by sync or backup systems, or prove that
forensic recovery is impossible.

## Privacy Boundary

The command returns only aggregate counts and hashes needed to review the plan.
It does not return:

- filenames or relative paths;
- file contents;
- the workspace or target absolute path; or
- values from old prompts, mailboxes, configuration, receipts, or secrets.

This command is CLI-only. It adds no MCP writer, UI, provider call, network call,
archive migration, zet or objet mutation, index change, or external-tool update.

## Security References

These references explain the risk classes behind the narrow contract; they do
not certify this WOM implementation:

- [CWE-22: Improper Limitation of a Pathname to a Restricted Directory](https://cwe.mitre.org/data/definitions/22.html)
  explains why caller-controlled paths must not escape the intended root.
- [CWE-59: Improper Link Resolution Before File Access](https://cwe.mitre.org/data/definitions/59.html)
  explains why links and shortcuts that can resolve to another resource are
  blockers.
- [CWE-367: Time-of-check Time-of-use Race Condition](https://cwe.mitre.org/data/definitions/367.html)
  explains why a checked path can become unsafe before it is used.
- [Python `shutil.rmtree` documentation](https://docs.python.org/3/library/shutil.html#shutil.rmtree)
  documents whole-tree deletion and notes that resistance to symlink attacks is
  platform-dependent. WOM therefore does not treat one high-level recursive
  deletion call as sufficient authority or proof of safe scope.

## Related Decisions

- [v0.3.307 decision](archive-infra-decision-log-2026-08-08-v03307-legacy-coordination-cleanup.md)
- [v0.3.307 release note](releases/v0.3.307.md)
- [v0.3.306 retired-integration decision](archive-infra-decision-log-2026-08-08-v03306-mow-harness-sunset.md)
- [Artifact Hygiene](artifact-hygiene.md)
