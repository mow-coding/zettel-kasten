# 2026-06-16 v0.3.58 Runtime Canonical Entry Points

## Context

After v0.3.57 made the running WOM-kit version explicit, the next field-feedback
gap was canonical entry/source orientation. An AI runtime entering an archive
needs to know which archive-relative files are authoritative before it reads
workspace data or mistakes a mirror/export for the source of truth.

## Decision

Implement a read-only `canonical_entrypoints` block inside
`archive runtime-context <archive-root> --format json`.

The block names `archive.yml` as the start-here file and reports the role,
kind, required flag, presence status, and source for local agent instructions,
identity context, source/provider bindings, canonical zets, draft inbox, object
manifest, derived-text manifest, saved views, and schema context.

## Safety Boundary

The new flow reads no file bodies, writes no files, calls no providers, reads no
secrets, and returns archive-relative paths only by default. It does not
implement migration enforcement, live provider sync, credential retrieval, IMAP
execution, or automatic export disambiguation.
