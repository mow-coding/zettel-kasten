# Decision Log: Aggregate Full-Doctor Edge Progress

Date: 2026-07-12
Decision: accepted for v0.3.227

## Context

The v0.3.225 targeted filename index and per-source candidate loading removed a
real all-receipt JSON bottleneck. On a real 8,583-zet archive, the index handled
21,539 receipt filenames in about 2.3 seconds. The now-fast per-source batches,
however, each emitted their complete progress lifecycle, producing hundreds of
compact stderr lines in seconds and preventing the operator from reaching the
final result comfortably.

## Decision

- Keep every validation read and result unchanged.
- Time-coalesce compact filename-index milestones to start, 10-second
  heartbeat when needed, and done.
- Aggregate targeted source loads across the whole Doctor run as sources,
  candidate documents opened, and `cache_hits`.
- Keep the aggregate alive across surrounding outer receipt events and close it
  with one final summary when Doctor finishes.
- Route each source batch to the `edge-receipt-source-load-detail` stage,
  suppressed by compact stderr but retained by verbose output and private
  progress logs.
- Accept only a fixed count-only aggregate message shape in the shared reporter.
- Do not add a broad pass to predict a dynamic final source count.

## Consequences

Default AI/runtime progress remains useful and bounded while maintainers keep
the complete trace on opt-in private surfaces. A synthetic event replay gives
deterministic output-volume evidence and conservative in-memory formatting
timings without reading a real archive or calling a provider.
