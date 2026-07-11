# Project Version Update

Status: implemented in v0.3.215

## Plain-Language Purpose

A WOM project can have three version states that drift apart:

1. the WOM-kit code currently loaded by Python;
2. the project-local code copy at `.zettel-kasten/source`;
3. one or more small files that remember the intended version, called pins.

Previously, a human had to receive update files with Git, move the local code to
the release tag, and edit the pin by hand. `project-version-update` turns those
steps into one reviewed transaction with explicit evidence and rollback.

It updates the tool around the archive. It does not rewrite the user's zets,
objets, manifests, source material, or external database.

## Safe Workflow

First preview. This performs no fetch and writes nothing:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --dry-run `
  --progress `
  --format json
```

The target may not exist locally yet. In that case
`ready_to_fetch_on_approve` means only that local preconditions passed and the
approved command will fetch and verify the release before any checkout.

After a human reviews the preview:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --approve `
  --reviewed-by <actor> `
  --progress `
  --format json
```

## What Approval Verifies

Before changing the checked-out source or a pin, WOM-kit requires:

- an existing project or archive root;
- the exact project-local `.zettel-kasten/source` directory;
- that directory to be the root of a Git working tree;
- no tracked edits and no unknown untracked files;
- a non-tracked local `installed-version.txt` as the only allowed untracked
  mirror file;
- no symbolic-link metadata directory, source mirror, pin, or receipt route;
- a configured Git remote named `origin`;
- an exact stable `vMAJOR.MINOR.PATCH` target that is not a downgrade;
- no existing update lock.

Approval then uses one non-force, atomic Git fetch for only:

```text
origin main -> refs/remotes/origin/main
origin exact target tag -> the same local tag
```

A colliding local tag is not force-overwritten. Raw Git stderr and the remote
URL are not copied into WOM output or receipts.

The fetched target must:

- be an annotated tag;
- resolve to a commit reachable from fetched `origin/main`;
- contain the target version in `wom-kit/pyproject.toml`;
- contain the same version in the package init;
- contain the same version in the repository-root package shim.

This proves agreement with the project's configured origin and main history. It
does not prove a cryptographic tag signature. The result and receipt say so.

## Apply And Receipt Order

After verification, WOM-kit:

1. checks out the exact tag in detached mode with ignored-file overwrite
   disabled;
2. verifies the resulting commit and all three source versions;
3. atomically writes the canonical project pin and any recognized existing
   mirror or legacy project pin;
4. verifies every pin byte;
5. validates and writes one receipt under
   `.zettel-kasten/receipts/version-updates/`;
6. removes the exclusive update lock.

The receipt is written last. It records commits, target, reviewer, changed pin
roles, configured-origin evidence, restart requirement, and privacy guards. It
contains no local absolute path, remote URL, raw Git error, or credential value.

## Failure And Rollback

If anything fails after checkout or pin writes, WOM-kit attempts to restore:

- the original branch and commit, or the original detached commit;
- the exact original bytes and existence state of every recognized pin;
- any partially written receipt and newly created empty receipt directories;
- the transient update lock.

Fetched refs may remain. They are discovery/version metadata, not the canonical
working checkout or user memory. The result distinguishes
`failed_rolled_back` from `failed_rollback_incomplete`; never claim success from
either state.

## New Process Required

Python cannot replace the already imported WOM-kit module in the middle of this
command. Therefore success is `updated_restart_required`, not simply
`updated`.

Close that invocation, start a new process from the project source mirror, and
run:

```powershell
archive version <project-or-archive-root> --format json
```

Claim the target runtime active only after the new result shows the intended
running version, import origin, source versions, exact head tag, and pins in
agreement.

## Bootstrap Boundary

The updater first ships in v0.3.215. An older installation cannot run a command
it does not yet contain. It needs one final update through its existing/manual
verified procedure to reach v0.3.215. Use `project-version-update` for releases
after that bootstrap.
