# Decision: v0.4.10 is a two-decision authenticated batch pipeline

Date: 2026-08-27

## Context

Letter 146 is excluded from new implementation judgment until its client
installs v0.4.9 and retests. Letter 147 confirms the separate problem that the
safe single-file route does not make ordinary multi-item intake practical.

## Decision

- Open only bounded 1–1,000 item local `source-intake-batch` and its generated
  `objet-capture-batch` handoff. Require every batch source to be
  archive-relative so a successful intake always leaves N receipts plus one
  generated request; keep external metadata intake on the v0.4.9 single route.
- Ask the person for one intake decision and one capture decision. WOM owns
  counts, hashes, exact targets, drift checks, evidence authentication, and
  independent verification.
- Bind capture to the authenticated succeeded intake claim, checkpoint chain,
  final receipt, current receipts and bytes, and same archive identity. An
  unkeyed self-consistent JSON document is not authority.
- Allow same-claim resume for unchanged checkpointed intake. Require a fresh
  exact dry-run and new approval for interrupted or partial capture; never
  auto-retry it or claim a checkpoint boundary the capture service lacks.
- Let WOM discover one authenticated intake resume from the unchanged manifest
  and reviewer without asking for internal ids. Fail closed on zero, multiple,
  forged, cross-archive, or wrong-project-runtime candidates.
- Use separate batch-specific native operation identities and bind them through
  the lower writers and durable receipts. Keep reconcile read-only, publication
  create-only, and uncertain post-write reporting truthful.
- Classify only `exact_human_approval_state_unknown` as a possibly mutated
  outcome. Native approval-dialog and workflow argument/contract failures occur
  before the domain writer and therefore report zero possible writes without a
  false resume or reapproval instruction.
- Treat the measured 508- and 1,000-item sub-43-second planning results as the
  v0.4.10 performance gate. Defer remaining per-item Windows reconstruction
  caching to v0.4.11.
- Remove runtime source-integrity subprocess fan-out without weakening the
  clean-snapshot recheck. Read each tracked Python file through the existing
  bounded real-file reader, enforce 32 MiB per file and 128 MiB total, and
  compute the exact Git blob OID locally from `blob <size>\0<bytes>`. Keep the
  12-second Git probe budget and fail closed on missing, oversized, unreadable,
  invalid-OID, or mismatched bytes.
- Keep the client archive read-only during development and release. Publishing
  or installing the wheel is not client execution evidence.

## Consequences

v0.4.10 reduces repeated human approval without weakening exact authority or
turning capture into publication. External sources, provider calls, uploads,
link inference, drafts, and minting remain outside this pipeline. The public
release may describe bounded synthetic counts and timings but contains no
client payload, private path, credential, or private feedback body. Remaining
per-item Windows reconstruction, generic ancestor-handle portability, and
safe-publication support on filesystems without hard links are deferred
hardening; unsupported publication blocks rather than overwrites.
