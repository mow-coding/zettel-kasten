# Credential Capability Contract

Status: implemented in v0.3.320 for the approved Notion page-recovery worker
Date: 2026-08-15

This document defines the narrow authority that must exist before WOM can read
one already-registered Notion credential for one approved recovery invocation.
It is a compatible security hardening of the existing
`notion-page-recovery` command, not a new command and not a password manager.

## Beginner summary

Think of the capability as a one-use ticket:

```text
human approves one unchanged recovery plan
-> parent creates a fresh one-use ticket
-> isolated worker proves that the ticket matches that exact plan
-> worker permanently stamps the ticket as used
-> only then may the broker read the exact registered credential
-> every provider request must stay inside the ticket's scope and budget
-> the worker finishes the audit record as succeeded or failed
```

The ticket contains no password, PAT, token, page body, page title, provider
response, local absolute path, or provider URL. The bearer value stays inside
the isolated worker's mutable secret wrapper and is never returned to AI, the
parent process, result JSON, or logs.

## Implemented v0.1 authority

The parent issues `wom-kit/credential-capability/v0.1` only after the normal
human approval has matched the exact recovery-plan digest. The document binds:

| Field | Exact v0.1 rule |
| --- | --- |
| `capability_id` | Fresh `cap_` plus 128 random bits; never reused. |
| `provider` | `notion` only. |
| `operation` | `notion_page_recovery_read` only. |
| `consumer` | `wom:workflow:notion-page-recovery` only. |
| `approval_decision` | `approve_once` only. |
| `allowed_methods` | `GET` only. |
| `endpoint_classes` | `retrieve_page` and `retrieve_page_as_markdown` only. |
| `required_registered_capabilities` | `read_content`, `retrieve_page`, and `retrieve_page_as_markdown`. |
| request binding | Exact recovery `request_sha256`. |
| plan binding | Exact recovery `plan_sha256`. |
| reviewer binding | Exact approved `reviewed_by`. |
| scope binding | Exact selected credential id, workspace fingerprint, authenticated receipt digest, and lifecycle revision. |
| time binding | UTC issue and expiry timestamps; default TTL 900 seconds, accepted range 30–3600 seconds. |
| use binding | `max_uses` is exactly `1`. |
| request budget | Exact bounded logical provider-attempt ceiling derived from the selected-item count and fixed retry/tree limits. |

Unknown fields, missing fields, wrong types, unsorted or duplicate values,
changed bindings, expired tickets, unsupported methods/endpoints, and impossible
budgets fail closed with content-free reason codes.

`expires_at` is the deadline for creating the durable claim, not a mid-run kill
timer. Once a valid claim is committed before that deadline, the bounded
invocation may finish under its fixed endpoint/scope/request budget and durable
claim state. A delayed worker cannot create a new claim after expiry.

## What “one use” means

One use means one explicitly approved spawned recovery invocation. It does not
mean one HTTP request. A single selected page may require bounded metadata,
Markdown, child-block, and retry requests. Those requests share the ticket's
separate `max_provider_requests` budget.

The worker claims the capability by exclusively creating:

```text
profiles/local/credential-capabilities/claims/<capability_id>.json
```

The archive authentication key protects the claim with a domain-separated
HMAC. The claim is created before the first native credential read. If any leaf
already exists for that capability id—even a malformed, partial, tampered, or
unfinished leaf—the id is permanently spent and replay is rejected. Failure or
process interruption does not make the same id reusable. A person may retry the
same unchanged plan only through a new explicit approval invocation that mints
a fresh capability id.

## Exact worker order

For a live provider slice, the isolated worker must preserve this order:

1. Recompute the archive identity, request digest, plan digest, selected scopes,
   reviewer, expiry, and request budget without reading a provider secret.
2. Acquire only the exact archive authentication-key target.
3. Create the exclusive authenticated capability-use claim.
4. Authenticate the selected credential receipt and lifecycle state, including
   active/current/default status and all three registered capabilities.
5. Read the exact native Windows Credential Manager target into an owned
   mutable buffer and verify its fingerprint.
6. Before every logical Notion transport attempt, reauthenticate the durable
   claim, revalidate current receipt/lifecycle authority, and spend one allowed
   endpoint/scope budget unit. The HTTP adapter performs exactly one transport
   attempt per authorized call; workflow retry requires another authorization
   and cannot hide extra adapter-internal attempts.
7. Close and wipe the bearer wrapper, then finalize the claim as `succeeded` or
   `failed` with only a fixed content-free failure code.

Any capability failure before step 5 keeps native credential reads and provider
requests at zero. A claim-finalization failure is not projected as success.

## Safe audit linkage

Three different artifacts carry three deliberately different projections:

- the HMAC-authenticated claim ledger records `capability_id`, capability
  digest, `request_sha256`, `plan_sha256`, budgets, final status, and authorized-
  request count;
- the durable recovery receipt records only a
  `wom-kit/credential-capability-reference/v0.1` object with schema, capability id,
  and capability digest;
- the parent result records the secret-free
  `wom-credential-capability-use-summary/v0.1` with capability id/digest,
  claim-created state, one-use ceiling, authorized-request count, and fixed
  status.

The parent accepts the child's result summary only when it matches the
capability it issued and the trusted recovery projection. The shared id/digest
links all three artifacts; request/plan digests remain in the authenticated
claim ledger instead of being copied into the recovery receipt or parent
summary.

This allows crash or IPC-loss reconciliation without recording a MAC, archive
authentication key, native backend target, credential id, workspace fingerprint,
receipt path, page id, anchor UUID, bearer value, or provider response.

The shared use-summary vocabulary is
`wom-credential-capability-use-summary/v0.1`. Registry/child state may be
`started` internally, but the trusted parent projection never accepts
`started`: it accepts only `not_required`, `rejected`, `unknown`, `succeeded`,
`failed`, or `finalization_failed` under their exact causal invariants. Missing
or untrusted child evidence projects `unknown` rather than guessing that a
started claim finished.

## Verified replay

If the recovery preview proves every selected object already exists with the
expected content hash, `provider_pending_count` is zero. The worker then uses
never-provider and never-broker sentinels, creates no capability claim, reads no
credential, and makes no provider request. The safe summary says
`status: not_required` and `claim_created: false`.

If that verified replay state changes between preview and execution, WOM blocks
instead of silently switching into a live provider path.

## Aside research boundary

Aside's public product page describes three useful product-level ideas: secrets
stay invisible to the AI, access is scoped to the task, and each credential use
is logged; it also describes human confirmation for sensitive actions. WOM
reused that general broker pattern, not Aside code, storage design, cryptography,
or browser integration.

Aside's public terms describe the service and its code/product materials as
owned by Aside or its licensors. No open implementation or technical protocol
was used as a dependency or copied into WOM. WOM's capability document, HMAC
claim ledger, exact Notion scopes, native Windows credential target, and tests
are independent repository-native work.

References:

- [Aside product page](https://aside.com/)
- [Aside Terms of Service](https://aside.com/policy/terms)

## Still not implemented

v0.3.320 does not add a generic vault broker, browser autofill, passkey flow,
payment/message/post approval UI, new popup, password-manager import, credential
sharing, multi-provider capability protocol, capability delegation, background
worker, remote audit service, or MCP write/execute tool. The older generic
`credential-access-broker-plan` and `credential-access-approval` surfaces keep
their existing planning/receipt semantics and do not become live secret access.

No source test proves a live credential registration, live provider acceptance,
completed 620-page recovery, merge, external CI, tag, GitHub Release, wheel,
fresh installation, or human acceptance.
