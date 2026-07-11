# Archive Infrastructure Decision Log: v0.3.223 Full-Doctor Phase Coalescing

Date: 2026-07-12
Status: accepted and implemented

## Context

v0.3.222 made normal archive entry fast and stopped repeated compact lines.
During an explicitly requested full Doctor, however, one mint receipt can hold
the outer count while hashing or building an edge-receipt index. Heartbeat kept
the count but did not say which safe class of internal work was active.

The content-free reporter also continued invoking its formatter for every raw
same-count substep before downstream compact suppression.

## Decision

- Reduce mint-receipt detail to nine fixed content-free phase labels.
- Put the current phase in heartbeat only; never echo the raw source message.
- Unknown messages produce no phase; path-like source text is never copied.
- Forward generic progress once per stage/count and use later substeps only to
  update heartbeat phase state.
- Preserve direct Doctor verbose and private progress-log detail unchanged.

## Consequences

An operator can distinguish a long file hash from an edge-index build without
seeing private archive identity. The shared reporter avoids repeated formatter
and output-lock work, but Doctor still performs every validation and file read.

No archive schema, zet, receipt, manifest, provider, credential, or write
boundary changes.
