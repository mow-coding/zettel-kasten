# Decision: v0.4.13 release and client-recovery boundary

## Context

R2 preservation code can make client-side recovery possible, but publishing code is not proof that a private client archive has been preserved.

## Decision

- Release v0.4.13 only after exact candidate-wheel verification and all required pull-request CI gates pass.
- Keep the development session read-only toward beta-client archives, credentials, providers, and feedback ledgers.
- Require the client-side project runtime to execute the approved operation and return terminal receipts before declaring the corresponding feedback resolved.
- Keep the 180-second Doctor scale threshold unchanged; use the designated Ubuntu CI gate as the authoritative platform result.

## Consequences

- The public release can be completed without silently mutating a client's machine or data.
- A successful release is reported as “client-ready,” not “client data recovered.”
- Client acceptance remains an explicit next stage with durable evidence.

Longer record: [meeting-minutes/2026-08-29-v0413-r2-release-candidate.md](meeting-minutes/2026-08-29-v0413-r2-release-candidate.md)
