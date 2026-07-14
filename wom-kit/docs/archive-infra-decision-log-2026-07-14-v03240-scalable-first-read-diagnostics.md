# Decision: Scale First-Read Diagnostics From Real-Archive Evidence

Date: 2026-07-14
Status: Accepted for v0.3.240

## Context

A real archive completed v0.3.239 first-read readiness, abstract freshness,
and revision audit without writes or private-content exposure. The freshness
command remained live but spent most of its time opening receipt JSON files
that could never contribute abstract review evidence. Its two independent ETA
sequences also made the first stage's zero ETA look like whole-command
completion. First-read readiness separately used a non-ready state as both a
readiness verdict and command failure.

## Decision

1. Scan current canonical zets before receipt evidence.
2. For safe explicit-abstract ids, probe only their deterministic mint and
   promotion receipt names, plus bounded canonical-revision and abstract-
   backfill directories.
3. Fall back to bounded publication-directory scans when a target lacks a safe
   id; never trade completeness for speed.
4. Rebuild this candidate route on every run and create no persistent cache.
5. Declare the freshness command's two content-free progress stages as
   `stage=1/2` and `stage=2/2`.
6. Make first-read schema v0.2 separate successful diagnostic execution from
   the readiness verdict.
7. Limit the first legacy abstract backfill exercise to a reviewed three-zet
   pilot using the existing plan/write/revert/audit contracts.

## Consequences

Freshness remains one canonical pass and one evidence-candidate pass, but it no
longer enumerates or opens unrelated provider, migration, upload, or diagnostic
receipts. An unsafe explicit-abstract target retains a conservative fallback.
Operators can distinguish stage completion from command completion, and shell
automation can distinguish execution success from `readiness_met` without
parsing a nonzero process exit as a crash. No canonical bytes, receipts, cache
files, provider state, or external database are changed by either diagnostic.
