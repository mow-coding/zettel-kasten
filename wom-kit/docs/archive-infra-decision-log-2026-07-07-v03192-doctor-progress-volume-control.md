# Archive Infra Decision Log - v0.3.192 Doctor Progress Volume Control

Date: 2026-07-07

Release: v0.3.192

## Context

The v0.3.191 edge-evolution progress patch successfully localized a previously
quiet doctor phase. On large archives, however, the full receipt-level progress
stream can overwhelm an AI operator's terminal and context window before the
full doctor run finishes.

The problem is not a failed diagnostic. It is an operator-channel ergonomics
problem: default progress should reassure and localize, not flood.

## Decision

Make `doctor --progress` compact by default.

The compact stream preserves stage boundaries, receipt milestones,
quiet-interval liveness, key edge-index lifecycle events, and ETA warm-up. The
full receipt-level trace remains available via `--progress-detail verbose`.

Add `--progress-log <path>` to write the complete progress event stream as JSONL
without forcing every event into stderr.

## Consequences

- Large full-archive doctor runs should be easier to operate from AI terminals.
- Debuggability is preserved through opt-in verbose stderr and JSONL progress
  logs.
- Result JSON, diagnostics, receipt semantics, manifests, and archive files are
  unchanged.
