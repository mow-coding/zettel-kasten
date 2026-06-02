# Work Log: v0.2.57 Capability Matrix And README Readability

Date: 2026-06-02
Branch: `codex/v0.2.57-capability-matrix-readability`

## Goal

Close a readability gap before adding more preview surfaces.

The review signal was clear: the WOM direction is coherent and safety-first, but the public entrypoints needed a simpler map of what exists, what only previews, what writes with approval, and what is still future work.

## Implemented

- Added `wom-kit/docs/capability-matrix.md`.
- Updated README release lists so `v0.2.55` is visible between `v0.2.56` and `v0.2.54`.
- Replaced the long top-level README status wall with a shorter summary and a pointer to the capability matrix.
- Added v0.2.x closing-plan language and a proposed narrow v0.3.0 boundary.
- Updated public release, upgrade, changelog, version, and citation metadata.
- Added focused documentation tests for the capability matrix and README tag sequence.

## Review Context

The public-safe summary of the external review is:

- overall recommendation: `GO WITH CAUTIONS`,
- vision: coherent,
- safety-first design: credible,
- risks: preview ladder fatigue, README readability debt, missing README v0.2.55 tag, and platform test brittleness,
- suggested direction: close v0.2.x with readability, shared-update indexing, and transport threat modeling before a narrow v0.3.0 approved-write boundary.

The full review text was not copied into public docs.

## Safety Notes

- No product CLI command was added.
- No MCP tool was added.
- No archive service behavior was added.
- No provider, transport, trust, import, attestation, signature, anchor, payment, blockchain, token, worker, or full-auto behavior was added.
- The batch is documentation, metadata, and test coverage only.

## Deferred

- Shared-update review index.
- ZET transport threat model and would-transport dry-run plan.
- Any receiver-side approved write boundary for v0.3.0.
