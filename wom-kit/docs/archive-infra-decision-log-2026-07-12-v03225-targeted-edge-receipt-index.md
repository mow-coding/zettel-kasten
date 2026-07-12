# Archive Infrastructure Decision Log: v0.3.225 Targeted Edge Receipt Index

Date: 2026-07-12
Status: accepted and implemented

## Context

Full Doctor already cached one global edge-receipt index, but constructing that
index opened every `*.zettel-edge.json` document when the first historical mint
target SHA was encountered. A local 8,583-receipt reproduction measured
104.226 seconds for that index despite only 4.181 seconds of fixture generation.
Progress remained attached to the outer mint-receipt count.

## Decision

- Build one safe filename-only edge-receipt index per Doctor.
- Group generated receipt names by source zet filename segment without opening
  the receipt JSON corpus.
- For a mismatched source, load only its named candidates and any legacy
  receipt paths directly referenced by current edges.
- Validate each loaded receipt's kind, source path, and timestamp before it can
  participate in SHA evolution proof.
- Cache the loaded source result for later mint/retired-draft checks.
- Report separate content-free index and source-load count stages.
- Keep the all-receipt service available for batch operations whose contract
  genuinely requires a complete receipt map.

## Consequences

The first mismatch still inventories every edge-receipt filename, but it no
longer opens every receipt document. The bundled temporary benchmark completes
an 8,583-name Doctor lookup while proving one index build, one target load, and
a second-lookup cache hit. This removes the reproduced computation bottleneck;
it does not claim that every other full-Doctor stage or every real filesystem
has a fixed completion time.

No archive schema, receipt schema, provider, credential, authority, migration,
or write boundary changes.
