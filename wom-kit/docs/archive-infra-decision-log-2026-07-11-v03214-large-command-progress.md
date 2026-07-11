# Decision Log: v0.3.214 Large-Command Progress And Bounded Output

Date: 2026-07-11
Status: implemented

## Decision

Give `ai-start-here`, `upgrade-check`, and CLI `zet-catalog` one opt-in,
content-free progress contract and one scratch-scoped full-result writer.

## Context

On a large real archive, these read-only commands can spend a long interval in
Doctor or frontmatter scanning before printing their final result. Silence makes
normal work indistinguishable from a hang. Printing raw trace messages would
create a path and content disclosure risk, while printing full JSON and progress
to the same stream would break automation.

## Consequences

- Progress goes to stderr and the final result stays on stdout.
- Stage boundaries, safe counts, elapsed time, warming-up ETA, and a 10-second
  heartbeat establish liveness without exposing archive content.
- Optional full-result output is confined to a new JSON file below
  `.wom-scratch/diagnostics/`, refuses overwrite, and is explicitly not a WOM
  record or receipt.
- The output file may contain private command results and must not be committed.
- Catalog scan counts make repeated CLI work visible, but v0.3.214 adds no
  persistent cache and claims no cross-process performance fix.
