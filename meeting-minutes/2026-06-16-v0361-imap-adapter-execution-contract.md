# 2026-06-16 v0.3.61 IMAP Adapter Execution Contract

## Context

Users are waiting for IMAP progress, but the safe path still requires one more
non-secret layer before any live adapter can connect to mailboxes.

The project already has IMAP source planning, operation request packaging,
adapter manifest planning/writing, readiness checks, selection planning, audit
planning/writing, and preflight checks. The next narrow step is to define what
a future live adapter is allowed to do after preflight passes.

## Decision

Add `imap-mailbox-adapter-execution-contract` as a read-only CLI command.

The command wraps the existing preflight result and returns a contract only when
preflight is ready. It defines future runtime inputs, future allowed actions,
AI-visible output rules, and a future execution receipt shape.

## Safety Boundary

The command does not open IMAP, log in, select/search a mailbox, list messages,
read headers/bodies/attachments, retrieve credentials, call providers, write
receipts, or write files.

The live adapter remains future work. This release only fixes the execution
boundary before implementation.
