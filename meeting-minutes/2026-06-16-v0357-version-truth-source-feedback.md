# 2026-06-16 v0.3.57 Version Truth-Source Feedback Response

## Context

The latest field feedback highlighted that the IMAP and credential-adapter
scaffolding is safer and more complete, but several user-facing gaps remain:

- live IMAP execution is still future work after the current approval gates,
- agents need a canonical "start here" signal before reading project data,
- extraction workflows need explicit coverage/completeness signals,
- credential extraction needs a semantic recipe for multi-account and
  multi-secret notes,
- large media exports need warning and text-focused alternatives,
- two visible WOM-kit locations can confuse a human or AI about which version is
  current.

The feedback was treated as private input. Public documentation should describe
the product problem without copying private paths, personal workspace names, or
raw feedback text.

## Decision

For v0.3.57, implement the lowest-risk public-safe slice first: a read-only
WOM-kit version truth-source checkpoint.

The checkpoint exposes:

- `archive --version`,
- `archive version [inspection-root] --format text|json`,
- `runtime-context` field `wom_kit_version`.

It uses `wom_kit.__version__` as the package source of truth, checks
`wom-kit/pyproject.toml` when available, and can compare an optional project pin
such as `.zettel-kasten/source/installed-version.txt`.

## Safety Boundary

The new flow writes no files, calls no providers, reads no secrets, and redacts
local absolute paths by default. It does not implement automatic upgrade,
installer repair, live IMAP execution, provider sync, credential retrieval, or
project migration.

## Remaining Work

Next candidate slices are canonical source/start-here enforcement, extraction
coverage receipts, credential semantic extraction recipes, text-only export
warnings, and the actual IMAP execution adapter after the safety gates are
ready.
