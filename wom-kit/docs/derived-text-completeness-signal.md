# Derived Text Completeness Signal

Status: v0.3.59 read-only derived text completeness signal checkpoint

`derive-text coverage` already checks whether manifested textual objets have
derived text. v0.3.59 adds a separate `completeness_signal` block so an AI
runtime does not confuse that manifest-scoped check with proof that an external
workspace, mailbox, cloud drive, or export was fully mirrored.

## Command

```powershell
archive derive-text coverage <archive-root> --dry-run --format json
archive derive-text-coverage <archive-root> --dry-run --format json
```

The result now includes:

```text
completeness_signal.scope_kind = manifest_scoped
completeness_signal.full_mirror_claimed = false
completeness_signal.full_mirror_proof_present = false
```

## What It Can Say

The signal can say:

- how many object manifest records exist,
- how many derived-text records exist,
- how many textual candidates are covered,
- how many textual candidates are missing derived text,
- how many textual candidates need a password or encrypted-file resolution.

This is useful for an extraction pass over known, manifested objets.

## What It Cannot Prove

The signal cannot prove:

- an external workspace was fully exported,
- a mailbox was fully mirrored,
- a cloud drive was fully mirrored,
- a Notion or workspace account has full account coverage,
- no unmanifested local files remain.

Those claims need a separate human-reviewed mirror/export receipt.

## Privacy Boundary

The signal is read-only and non-secret:

- it reads no source file bodies,
- it scans no external workspaces,
- it calls no providers,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it writes no files,
- it echoes no local absolute paths.

## Not Implemented

v0.3.59 does not create full mirror manifests, run Notion/mail/cloud-drive
exports, scan local folders, call providers, or decide that an external account
has complete coverage. It only prevents the derived-text coverage gate from
being misread as a full-mirror proof.
