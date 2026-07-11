# Archive Infrastructure Decision Log: v0.3.222 Quick Start And Honest Progress

Date: 2026-07-12
Status: accepted and implemented

## Context

A real 8,583-zet archive confirmed that progress and heartbeat fixed the former
silent wait, but `ai-start-here` still took more than six minutes because it
always ran the complete Doctor. The mint receipt stage also converted many
internal substeps for receipt one into repeated compact `1/N progress` lines.

The prior result additionally claimed no zet or objet body reads even though
the automatic full Doctor could read both. A read-only command still needs an
accurate description of what it reads.

## Decision

- Make bounded identity/authority/entrypoint/operating context the quick default.
- Require explicit `--full-doctor` for the complete archive health scan.
- Put inspection mode, Doctor checked state, and claim boundary in the result.
- Record the broader content reads actually observed during full Doctor while
  distinguishing them from credential-store/provider access.
- In compact progress, suppress an unchanged stage/count for 30 seconds except
  for heartbeat.
- Carry the latest count in heartbeat and report unit, stage elapsed time, rate,
  and ETA. Define `mint-receipts` as counting mint receipt files.
- Keep verbose/progress-log detail available and keep all progress content-free.

## Consequences

An entering AI receives the start map quickly and cannot mistake it for a green
archive health report. Operators can still request the former complete check in
one command. Long receipt validation remains visible without terminal floods,
and the read boundary now matches actual implementation behavior.

No archive schema, zet, receipt, manifest, provider, or credential state changes.
