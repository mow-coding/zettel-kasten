# Archive Infra Decision Log - v0.3.188 Doctor Mint Receipt Heartbeat

Date: 2026-07-07

Release: v0.3.188

## Context

Large archive operators need `doctor --strict --progress` to prove where a long
read-only check is spending time.

v0.3.186 exposed detailed mint-receipt sub-steps for the first three receipts.
That narrowed a reported pause to the moment after the third receipt completed,
but the next progress line could still be far away because later detailed
receipt output was sampled only every 250 receipts.

The early ETA also used elapsed time from the whole doctor command, so the first
few mint-receipt samples could project an alarming and low-quality ETA.

## Decision

Keep dense sub-step output sampled, but add an always-on mint-receipt heartbeat:

- every mint receipt emits one receipt-level progress line;
- receipts 1 through 4 emit detailed sub-steps;
- every 250th receipt and the final receipt still emit detailed sub-steps;
- after receipt 4, doctor announces the switch to receipt heartbeat mode.

Progress ETA now uses per-stage elapsed time and reports `eta=warming_up` before
there are enough counted samples for a useful projection.

## Consequences

- Operators can see that doctor advanced beyond the first detailed samples.
- A slow later receipt is named by its archive-relative receipt path before its
  checks run.
- Optional `--progress` output becomes more talkative, but only on stderr.
- Result JSON, receipts, manifests, and archive diagnostics are unchanged.
