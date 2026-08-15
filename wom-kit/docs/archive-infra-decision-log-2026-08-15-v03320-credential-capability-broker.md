# Decision Log: v0.3.320 One-Use Credential Capability Broker

Date: 2026-08-15

## Context

Letter 118 already provided an authenticated receipt/lifecycle registry, an
exact Windows Credential Manager read, and a fixed read-only Notion adapter.
However, the live recovery path did not yet have a durable, invocation-specific
artifact proving why this exact worker was allowed to read the credential, how
long that authority lasted, whether it had already been spent, or how many
provider attempts it could authorize.

The user pointed to Aside's agent-oriented password manager as a useful product
reference. Aside publicly describes secrets invisible to AI, task-scoped access,
human confirmation at sensitive edges, and an access log. Its public materials
describe a proprietary product; WOM did not obtain an open implementation or
protocol to reuse. Only the general broker pattern informed this design.

## Decision

1. Harden the existing `notion-page-recovery` execution path in v0.3.320. Add
   no new CLI or MCP command and change no credential popup or store format.
2. After exact human approval, the parent mints a fresh secret-free
   `wom-kit/credential-capability/v0.1` document with a random 128-bit id.
3. Bind the document to provider `notion`, operation
   `notion_page_recovery_read`, consumer
   `wom:workflow:notion-page-recovery`, `GET`, two fixed endpoint classes,
   all three required registered capabilities, exact request/plan digests,
   exact selected receipt/lifecycle scopes, exact reviewer, TTL, one use, and a
   bounded provider-request budget.
4. Treat one use as one spawned approved recovery invocation, not one HTTP
   request. `max_uses` is exactly one; the provider-attempt budget is separate.
   Expiry is the claim-creation deadline only, and the adapter performs exactly
   one transport attempt per authorized call without a hidden internal retry.
5. Validate all caller-controlled bindings before native credential access.
   After acquiring the exact archive authentication key, the child must create
   an exclusive HMAC-authenticated claim before the first native secret read.
6. Any existing claim leaf permanently spends the id, regardless of whether
   that leaf is valid, malformed, partial, tampered, started, succeeded, or
   failed. Failure and crash do not reopen the id.
7. Reauthenticate the durable claim and exact receipt/lifecycle authority before
   every allowed provider attempt. Enforce registration capabilities as well as
   endpoint, scope, and budget bounds.
8. Finalize the claim as `succeeded` or `failed` with fixed content-free data.
   A finalization failure blocks a success projection.
9. Use a three-way content-free evidence contract. The HMAC claim records
   capability id/digest, request/plan digests, budgets, final status, and count;
   the durable recovery receipt records only reference schema plus capability
   id/digest; the parent result records the secret-free use summary. Shared
   id/digest values support crash or IPC-loss reconciliation without copying
   request/plan digests into the recovery receipt/result or disclosing page ids,
   credential values, local paths, provider bodies, or MACs.
10. Fully verified local replay creates no capability claim and performs no
    credential read or provider request. Any drift blocks rather than escalating
    to live execution.

## Consequences

- A missing, forged, changed, expired, over-budget, or replayed capability fails
  before provider work; failures before the claim/secret boundary preserve exact
  zero secret reads and zero provider attempts.
- The same reviewed plan can be tried again only with a fresh capability id
  created by a new approved invocation.
- The existing native popup remains the only live registration surface; this
  change neither asks the user to re-enter a key nor adds another UI.
- The older generic `credential-access-broker-plan` remains a read-only planner,
  and its generic approval receipt does not silently become live authority.
- Source and synthetic tests do not prove real registration, provider
  acceptance, archive recovery, merge, CI, release, or installation.

## External reference boundary

Aside is cited only as a product-level reference for invisible-to-agent secret
use, scoped task authority, human confirmation, and access logging. Aside's
encryption, Secure Enclave, browser autofill, sandbox, storage, sync, and agent
implementation are not asserted, copied, or depended on by this repository.

References:

- [Credential Capability Contract](credential-capability-contract.md)
- [Credential Access Broker Plan](credential-access-broker-plan.md)
- [Letters 118 and 119](letter118-119-credential-continuity-and-notion-page-recovery.md)
- [Aside product page](https://aside.com/)
- [Aside Terms of Service](https://aside.com/policy/terms)
