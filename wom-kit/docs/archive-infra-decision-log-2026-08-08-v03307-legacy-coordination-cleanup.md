# Decision Log: Exact-Root Legacy Coordination Cleanup

Date: 2026-08-08
Status: accepted for v0.3.307
Related historical decision:
`archive-infra-decision-log-2026-08-08-v03306-mow-harness-sunset.md`

## Decision

Add one CLI-only, cross-platform no-write preview and Windows-only destructive
opt-in command for the direct `.mow-harness/` child of one exact,
human-supplied absolute workspace root:

```text
archive legacy-coordination-cleanup <absolute-workspace-root>
```

The command requires a no-write, content-free plan before approval. A Windows
approved cleanup is bound to the exact `plan_sha256`, a safe reviewer id,
workspace-owner authority, external-writer quiescence, and an affirmation that
the retired state is disposable. If backups or receipts are present, their
disposal requires a separate explicit affirmation.

`collab/` is never traversed or changed. Normal WOM discovery, Doctor, artifact
hygiene, restore, installation, project update, and upgrade do not invoke this
command or delete retired state.

## Why This Does Not Restore The Retired Integration

v0.3.306 retired the recommendation, repository link, compatibility guide, and
install/update/activation guidance for the unavailable external product. That
historical decision remains unchanged.

v0.3.307 does not identify, install, invoke, update, repair, activate, or migrate
that product. It implements a narrow local filesystem disposal boundary for an
owner who already knows the exact workspace root. No dependency, external CLI,
MCP surface, receipt parser, UI, or network lookup is added.

## Scope And Authority

The caller supplies an existing absolute workspace root. The only derived
candidate is its exact direct child named `.mow-harness`.

The command must not:

- search parent directories, drives, home directories, or sibling workspaces;
- accept the retired child itself as the workspace root;
- inspect or remove `collab/`;
- infer deletion authority from a folder name, age, dead URL, or version marker;
- remove Git-tracked data; or
- treat approval for one plan as approval for later filesystem state.

The workspace owner, not WOM, decides that the retired state is disposable.
Dry-run classification alone grants no deletion authority.

## Fail-Closed Boundary

Planning or approval blocks on unknown, unsafe, or incomplete evidence,
including:

- absent or non-absolute workspace authority;
- unsafe root selection, path escape, or case drift;
- tracked content;
- content tracked by any Git index at an ancestor of the workspace;
- any nested `.git` entry inside the target, rejected without traversal;
- a symbolic link, junction, Windows reparse point, or other special file;
- a Windows named alternate data stream;
- a Linux `mnt_id` mismatch or another unproven cross-mount entry;
- an existing cleanup lock or old cleanup tombstone;
- caller Git environment that could redirect repository or index selection;
- unreadable state;
- file-count or byte-limit exhaustion; and
- change between the reviewed scan and deletion.

The plan reports aggregate counts and hashes without filenames, contents, or
absolute paths. Its CLI planning states are `dry_run_ready`, `target_absent`, or
`blocked`. `--max-files` bounds scanned entries, including directories. Approval
repeats the same optional `--max-files` and `--max-bytes` ceilings when they were
part of the preview.

Dry-run is available on every supported platform and writes nothing. POSIX
plans report `approval_platform_supported: false` and `safe_to_cleanup: false`.
POSIX approval fails before lock acquisition and before mutation because
standard POSIX has no portable atomic primitive for deleting a pathname only if
it still names the exact reviewed inode.

## Mutation And Evidence Boundary

Approved mutation is Windows-only in v0.3.307. Windows retains handles to every
workspace ancestor and the workspace root for the complete transaction, then
uses a retained verified handle to dispose each exact approved file or empty
directory in place. This closes pathname-replacement gaps covered by the
implemented contract; external writers still must be quiescent.

The implementation creates no new tombstone rename. A pre-existing legacy
tombstone blocks planning or approval. Once the first mutation starts, any
partial or uncertain outcome is conservatively `partial_cleanup_pending`; it is
never relabeled as success and there is no automatic retry, resume, or rollback.

The command creates no backup and no cleanup receipt. Existing backup or receipt
bytes stay inside the human's disposal decision. When
`summary.backups_or_receipts_present` is `true`, approval requires the separate
`--affirm-backups-and-receipts-disposable` gate.

Deletion removes filesystem directory entries. It is not secure media erasure
and does not promise storage-block overwrite, backup/sync-copy removal, journal
purging, or forensic irrecoverability.

## Security References

- [CWE-22](https://cwe.mitre.org/data/definitions/22.html) informs the exact
  root and path-confinement boundary.
- [CWE-59](https://cwe.mitre.org/data/definitions/59.html) informs the strict
  link, junction, and reparse-point rejection.
- [CWE-367](https://cwe.mitre.org/data/definitions/367.html) informs plan reuse,
  change revalidation, and external-writer quiescence.
- [Python `shutil.rmtree`](https://docs.python.org/3/library/shutil.html#shutil.rmtree)
  documents whole-tree deletion and a platform-dependent symlink-attack
  resistance boundary. It is a library contract, not proof that an application
  selected the right target or closed every race.

These references describe relevant weakness classes and library behavior. They
are not a security certification of WOM.

## Consequences

- A human can review and remove one known retired-state tree without broad
  filesystem discovery; approved removal is Windows-only in v0.3.307.
- POSIX users receive the same bounded, content-free review evidence, but no
  mutation authority.
- Personal WOM records, zets, objets, indexes, provider state, and `collab/`
  remain outside the operation.
- Existing v0.3.306 archives require no migration.
- The defensive `/.mow-harness/` and `/collab/` ignore/quarantine rules remain in
  place after cleanup so missing paths stay harmless and future accidental state
  remains private.
