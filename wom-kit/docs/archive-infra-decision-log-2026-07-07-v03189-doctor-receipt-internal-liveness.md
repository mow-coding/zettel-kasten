# Archive Infra Decision Log - v0.3.189 Doctor Receipt Internal Liveness

Date: 2026-07-07

Release: v0.3.189

## Context

v0.3.188 added receipt-level heartbeat for `doctor --strict --progress`, proving
that doctor could advance beyond the first detailed mint-receipt samples.

The remaining blind spot was inside a non-sampled receipt. Doctor printed the
receipt path before checking it, but then stayed quiet while loading JSON,
checking file references, hashing referenced files, loading target frontmatter,
or comparing the target mint link.

For large private archives, that silence made a slow current receipt look like a
stalled next receipt or hidden global stage.

## Decision

Keep detailed sub-step sampling, but add minimal internal liveness for every
mint receipt:

- receipt checks started;
- source/target/snapshot file-ref checks named before they run;
- receipt checks completed;
- large referenced-file SHA-256 hashing can emit content-free still-hashing
  heartbeats.

Counted progress ETA keeps `warming_up` through the first nine samples or first
30 seconds of a stage.

## Consequences

- Operators can distinguish "current receipt file-ref/hash is slow" from "doctor
  did not advance to the next receipt."
- Large-file hash work has liveness without exposing file content or private
  locator values.
- Optional `--progress` stderr output is more verbose for mint receipts.
- Result JSON, diagnostics, receipt semantics, manifests, and archive files are
  unchanged.
