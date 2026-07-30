# Decision Log — v0.3.289 Exact Wheel Resource Integrity

Date: 2026-07-30

## Context

The release checker confirmed that a wheel carried a resource manifest and
the declared resource names. Presence alone could not prove that the manifest
was the reviewed manifest or that every installed resource contained the
reviewed bytes. Ambiguous ZIP members or malformed manifest input also needed
one explicit bounded failure contract.

## Decision

Treat the repository manifest, wheel manifest, wheel resource bytes, and
repository packaged mirror as four independently checked representations of
one exact resource set.

Reject duplicate or unsafe ZIP members and strict-manifest violations. Require
exact resource-set equality, declared and actual byte-count equality, SHA-256
equality, and byte-for-byte packaged-mirror equality. Normalize archive,
decoding, parsing, schema, and resource-read failures to `WheelCheckError`.

Model the installed-path boundary, not only exact ZIP strings. Reject Windows
case collisions, forbidden characters, trailing dots/spaces, reserved device
names, and every top-level wheel `.data` scheme member. The current artifact
is a pure wheel, so fail-closed `.data` rejection is safer than permitting
install-time `purelib` or `platlib` relocation onto verified resources.

Do not expand this claim into whole-wheel reproducibility or comparisons of
compression, ordering, timestamps, permissions, or offsets.

## Consequences

- A release wheel cannot pass merely because expected filenames exist.
- Reviewed package resources remain bound to both deterministic metadata and
  their actual installed bytes.
- Corrupt or ambiguous containers fail without raw parser or ZIP tracebacks.
- Cross-platform extraction aliases cannot overwrite a verified resource
  after the archive-level check passes.
- Release checking does more local I/O because every resource is read and
  hashed.
- Runtime archive, CLI, MCP, provider, and migration behavior is unchanged.

Implementation detail and verification evidence are recorded in
`meeting-minutes/2026-07-30-v03289-wheel-resource-integrity-implementation.md`.
