# Meeting Minutes: v0.3.320 Credential Capability Broker

Date: 2026-08-15

## Why this work started

The conversation began from repeated credential-input frustration. Ordinary
terminal input worked, but the secret-entry surface did not accept typing or
paste reliably and earlier Korean guidance was unreadable. The separate native
popup correction was completed in the preceding Letter 132 work. The user then
asked whether Aside's browser password manager could offer a better technical
model for the next boundary and asked to implement the useful part.

The intent was not to copy a browser or build a full password manager. The
immediate problem was narrower: WOM already knew how to keep an adopted Notion
credential outside AI and resolve it inside an isolated worker, but one approved
recovery invocation needed an explicit, expiring, one-use authority and durable
audit trail.

## Research interpretation

Aside's public site describes an agent-oriented password manager where
credentials are autofilled without exposing them to the AI, task access is
scoped, sensitive actions wait for human confirmation, and each access is
logged. Its terms describe the service and product/code materials as owned by
Aside or its licensors.

The team therefore treated Aside as a proprietary product reference, not an
open technical implementation. No Aside code, encryption scheme, browser
storage design, Secure Enclave integration, sync protocol, or agent runtime was
copied or added. The reusable idea was only:

```text
human approval
-> narrow secret-free authority
-> local broker uses the secret without returning it to AI
-> task-scoped enforcement
-> durable content-free audit
```

## Existing path audit

The live Letter 118 path was traced through the recovery CLI, spawned worker,
authenticated registry, exact native read, `NotionBearerSecret`, fixed Notion
HTTP adapter, and recovery executor. This confirmed several strong existing
boundaries:

- the parent process remained secret-free;
- receipt and lifecycle MACs selected one exact credential and workspace;
- the native backend target was derived from authenticated records;
- Notion access was fixed to read-only operations without redirects;
- the bearer buffer was owned, closed, and wiped inside the worker;
- recovery already bound the request, selected items, plan digest, and reviewer.

The audit also found the precise gap: there was no live invocation capability,
TTL, exclusive one-use claim, consumer/operation binding, registered-capability
enforcement at resolve time, or provider-attempt budget. An older generic
`CredentialUseBroker` concept passed a Python string to a callback and was not
connected to the real recovery path, so it was explicitly not adopted.

## Design decisions

The chosen v0.1 vertical slice is limited to the existing approved Notion page
recovery command:

- fresh `cap_` id with 128 random bits per approved invocation;
- fixed provider `notion`;
- fixed operation `notion_page_recovery_read`;
- fixed consumer `wom:workflow:notion-page-recovery`;
- `GET` only;
- endpoint classes `retrieve_page` and `retrieve_page_as_markdown`;
- required registered capabilities `read_content`, `retrieve_page`, and
  `retrieve_page_as_markdown`;
- exact request, plan, reviewer, selected scope, TTL, one-use, and bounded
  logical-provider-attempt bindings;
- default TTL 900 seconds, with the protocol accepting only 30–3600 seconds;
- a durable HMAC-authenticated exclusive claim before the first native secret
  read;
- permanent replay rejection for any existing capability-id leaf;
- fixed `succeeded`/`failed` finalization and safe unknown/finalization-failed
  projection;
- no claim at all for a fully content-hash-verified local replay.

One use means one approved spawned invocation. It cannot mean one HTTP request
because one page can require bounded metadata, Markdown, child-block, and retry
requests. Each of those logical attempts still spends the separate request
budget.

The TTL was fixed as a claim deadline only. A worker must create its claim
before expiry, but a successfully claimed bounded invocation is not terminated
mid-run by the clock. The adapter performs exactly one transport attempt per
authorized call; each workflow retry must spend another authorization.

## Security review correction

An independent security review found an important reconciliation gap in the
first claim-ledger draft: a claim containing only capability id/digest could
prove that authority was spent, but after a worker crash or lost IPC it would
not safely identify which approved recovery request and plan the claim belonged
to. It also required the recovery evidence to link back to the capability.

The implementation contract was corrected before freeze:

- the authenticated claim records `request_sha256` and `plan_sha256` in addition
  to capability id/digest;
- the durable recovery receipt stores only reference schema plus capability id
  and digest;
- the returned parent projection stores a separate secret-free use summary with
  claim state, one-use ceiling, authorization count, and fixed status;
- the parent validates that child summary against the exact capability it
  issued;
- none of those surfaces include page ids, credential values, workspace labels,
  native backend targets, local absolute paths, provider bodies, or MACs.

Shared capability id/digest values create three-way content-free reconciliation.
Request/plan digests, budgets, final status, and count remain in the HMAC claim;
the recovery receipt does not pretend to be a full use summary. This preserves
secret and archive privacy.

## Final diagnostic correction

The final independent audit found one safe but unnecessarily vague projection.
When the child parsed the exact parent-issued capability successfully but then
rejected it at its claim deadline, the child originally discarded the safe
capability id/digest from its rejected summary. The parent therefore reported
unknown worker state instead of the exact content-free
`credential_capability_expired` blocker.

The child now retains a successfully parsed capability only for its rejected
summary. The parent still accepts that summary only when its id and digest
match the exact capability held in the trusted parent contract. This preserves
explicit expiry diagnostics while malformed or changed child capability data
continues to project unknown. The correction happens before archive-key,
credential, or provider access, and a dedicated projection regression fixes all
three operation counts at zero.

## Implementation surfaces

The implementation added or updated these repository-relative surfaces:

- `wom-kit/src/wom_kit/credential_capability.py`;
- `wom-kit/schemas/credential-capability-v0.1.schema.json`;
- `wom-kit/src/wom_kit/credential_secure_registry.py`;
- `wom-kit/src/wom_kit/credential_workflows.py`;
- `wom-kit/src/wom_kit/notion_http_adapter.py`;
- `wom-kit/src/wom_kit/notion_page_recovery.py`;
- focused capability, registry, workflow, adapter, and recovery tests;
- this meeting minute, the v0.3.320 decision log, capability contract, release
  note, living operator documentation, and deterministic package resources.

The product keeps the existing CLI/MCP surface. There is no new command, no new
popup, no changed store format, and no generic password-manager integration.

## Explicit non-actions and evidence boundary

This implementation session used fake/injected credentials and temporary test
archives only. It did not request or receive a real secret, open the production
registration popup, read or write a real credential store, call Notion, operate
on any real archive, recover a real page, change a provider account, or inspect
private archive content.

Implemented source plus passing local tests can establish local contract
behavior. They do not by themselves establish merge, external CI, exact tag,
GitHub Release, wheel publication, fresh installation, live credential
registration, provider acceptance, completed 620-page recovery, or human
acceptance. The continuation committed and pushed the candidate and opened a
draft pull request. It did not merge, tag, publish a release or wheel, deploy,
or perform any live credential/provider/archive operation.

## Pull-request CI correction

After the implementation was committed and pushed as draft PR 69, the first
exact-head CI run found one deterministic documentation-version failure. The
English and Korean philosophy implementation evidence maps still identified
their current review as v0.3.319 even though their regression contract reads
the current WOM-kit version dynamically. Both status lines were advanced to
v0.3.320 without changing the historical v0.3.252 traceability checkpoint they
describe. No product behavior, capability authority, secret boundary, or
historical release artifact changed. The exact failing documentation test and
the current release-document groups were rerun before the follow-up push.

## References

- [Credential Capability Contract](../wom-kit/docs/credential-capability-contract.md)
- [Decision log](../wom-kit/docs/archive-infra-decision-log-2026-08-15-v03320-credential-capability-broker.md)
- [Aside product page](https://aside.com/)
- [Aside Terms of Service](https://aside.com/policy/terms)
