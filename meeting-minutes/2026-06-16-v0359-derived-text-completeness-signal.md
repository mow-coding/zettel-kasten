# 2026-06-16 v0.3.59 Derived Text Completeness Signal

## Context

After runtime canonical entrypoints, the next safe field-feedback gap was
coverage language. Existing derived-text coverage could show whether manifested
textual objets had derived text, but an AI could still overstate that as proof
that a full external workspace, mailbox, cloud drive, or export had been
mirrored.

## Decision

Add a read-only `completeness_signal` block to `derive-text coverage`.

The signal uses `scope_kind: manifest_scoped`, explicitly sets
`full_mirror_claimed: false`, and lists claims it cannot prove without a
separate human-reviewed source/export mirror receipt.

## Safety Boundary

The signal reads no source file bodies, scans no external workspaces, calls no
providers, reads no secrets, writes no files, and echoes no local absolute
paths. It does not implement full mirror manifests, provider exports, local
folder scans, or account-wide coverage proof.
