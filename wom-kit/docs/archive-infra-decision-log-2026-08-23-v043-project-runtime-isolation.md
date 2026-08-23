# Decision: v0.4.3 Project-Scoped Runtime Isolation

Status: implementation under audit correction; focused/full CI, release, and
real-project activation pending

Date: 2026-08-23

## Context

One Windows account may run several client project folders while a shared PATH
`archive.exe` is visible to all of them. Replacing that executable during WOM
development makes an unrelated client appear updated without its own action.

## Decision

`project-version-update` installs an exact public release wheel into
`.zettel-kasten/runtimes/vX.Y.Z/`, exposes the stable project-relative
`.zettel-kasten/bin/archive.cmd`, and keeps
`.zettel-kasten/installed-version.txt` as the only active project version pin.
The public-wheel SHA-256, release tag and commit, Python version, runtime
receipt, final new-process checks, previous/new pin values, and launcher are
bound into the exact approval and v0.3 update receipt.

The updater never changes PATH, never replaces the shared launcher, and never
deletes an older runtime during activation. An approved ordinary write whose
running version differs from the project pin fails before dispatch with
`project_runtime_mismatch`. Read-only version inspection and the exact target
wheel's approved updater bootstrap remain available.

The tagged policy also binds an exact dependency supply lock. For v0.4.3 the
supported installation target is CPython 3.12 on Windows x86-64. The updater
downloads the WOM wheel plus the locked PyYAML and unicodedata2 wheels, verifies
every declared size and SHA-256, and installs only those local artifacts with
pip isolation, index access disabled, and dependency resolution disabled. The
artifacts remain inside the versioned runtime so later reuse can recheck their
bytes, the installed payload, package resources, distribution inventory, and a
fresh process. An unsupported interpreter or platform fails closed; it does not
fall back to a live package index.

The updater's native approval dialog is inside the same lock-held transaction
as release preparation. Before the dialog, the updater fetches and fixes the
annotated tag object, peeled commit, `origin/main`, source HEAD, pin bytes,
runtime policy, supply lock, public WOM wheel, and materialization preflight.
After approval it performs no network operation. It rechecks the complete
snapshot before the first source, runtime, launcher, pin, or update-receipt
write.

## Consequences

- Each project changes version only through its own approved transaction.
- Another folder or session does not become updated merely because development
  or release verification occurred on the same Windows account.
- Failed activation can restore the old source, launcher, and pins and remove
  only transaction-owned runtime paths. Runtime-root state is independently
  compared with its pre-install snapshot; an unexplained orphan makes rollback
  incomplete and preserves the update lock.
- Runtime directories consume additional disk space until a separately
  reviewed cleanup policy exists.
- POSIX remains preview-only for the complete updater transaction.

Longer record:
`meeting-minutes/2026-08-23-v043-project-runtime-isolation-and-ci-repair.md`.
