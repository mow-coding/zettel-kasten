# Archive Infra Decision Log - v0.3.187 AI Artifact Lifecycle Inventory

Date: 2026-07-07

Release: v0.3.187

## Context

WOM already separates objets, derived text, draft zets, canonical zets, and
receipts. It also has explicit AI scratch cleanup for zets that reference
`.wom-scratch/` or `workbench/ai-scratch/`.

The missing operational surface was the before-cleanup state: AI-generated
working files and chat logs can accumulate before anyone decides whether they
should be preserved, distilled, linked, deferred, or discarded.

## Decision

Add read-only `archive ai-artifact-inventory --dry-run`.

The inventory scans only allowlisted AI artifact/scratch roots and returns
metadata-only candidate rows with a stable `artifact_ref`, inferred
`artifact_kind`, and current `fate_state`.

JSONL chat logs are treated as possible raw evidence to preserve as objets. They
are not treated as canonical zet bodies.

## Consequences

- Operators can ask "what AI artifacts are still unresolved?" without broad
  archive recursion.
- The command can feed a conversational status-board answer without requiring a
  web UI.
- The command reads no file bodies and calculates no content hashes.
- The command writes no files and deletes nothing, so it cannot silently clean up
  user material.
- By default, archive-relative paths are hidden; local operators can opt in with
  `--show-relative-paths`.

Future patches may add approval-gated fate records, but v0.3.187 intentionally
stops at a read-only inventory.
