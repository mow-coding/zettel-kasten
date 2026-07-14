# Archive Infrastructure Decision Log: v0.3.236 Canonical Revision Audit

Date: 2026-07-14
Decision: accepted for v0.3.236

## Context

v0.3.235 can atomically replace one canonical zet, preserve immutable
before/after evidence, and retain a private lock across process interruption.
One receipt can be verified during idempotent retry, but an operator still
needs an archive-wide answer about historical chains and leftover locks.

## Decision

- Add CLI-only, read-only `zet-revision-receipt-audit`.
- Validate every revision receipt's schema, archive identity, digest filename,
  reviewer shape, timestamp, edge-review contract, and abstract/body evidence.
- Group valid receipts by private canonical identity and trace one linear chain
  backward from the current canonical hash.
- Require adjacent file, semantic, abstract, and body hashes to agree and
  revision timestamps to increase strictly.
- Read each current canonical target at most once per identity; never resolve
  every receipt through a complete zet-tree scan.
- Read text-free private locks and distinguish completed, recoverable,
  prewrite, ambiguous, invalid, and unsupported states without deleting them.
- Return only counts, fixed codes, SHA-only handles, and an audit digest. Echo
  no private identity, path, text, reviewer, provider value, or secret.
- Do not add a duplicate MCP tool. The local CLI is already available to the
  AI operator and keeps the MCP list smaller.

## Consequences

WOM can now distinguish durable revision history from a pile of individually
valid-looking receipts. A new AI session can see whether memory corrections
form one continuous local chain and whether an interrupted transaction needs
receipt recovery, without loading the knowledge text into diagnostic output.

The audit repairs nothing. Because revision receipts retain hashes rather than
old content, canonical revert still requires a separate private restore
proposal that matches the recorded before state.
