# ZET Transport Threat Model And Would-Transport Plan

Date: 2026-06-02
Status: read-only dry-run preview

## Summary

v0.2.59 adds a conservative planning surface for future ZET transport.

It answers one narrow question:

```text
If real ZET transport existed later, what risks and human controls would this local shared update record require before transport?
```

The answer is a planning preview only. It does not send, deliver, publish, mirror, create keys, create radio-frequency access, create receipts, call providers, start queues/workers, update feeds, trust, import, attest, sign, anchor, or run real ZET transport.

## CLI

```powershell
python wom-kit\cli\archive.py zet-transport-plan <archive-root> --record <archive-relative-json> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json
```

The `--record` path must be archive-relative and contained under the archive root. Absolute paths, URL-like paths, traversal, UNC paths, and NUL bytes are rejected.

The command reads one local JSON record only. It first runs the v0.2.56 single-record shared update review preview policy. If that preview is blocked, the would-transport plan is blocked.

## MCP

The MCP tool is:

```text
zet_transport_would_plan
```

MCP accepts only `dry_run: true` as a JSON boolean. String values such as `"true"` and number values such as `1` are rejected.

MCP does not expose apply/write/send/deliver/publish/transport/import/trust/attest/sign/anchor/key/radio-frequency/mirror sibling tools.

## Method Risk Model

### key-sharing

Planning risks:

- key leakage,
- unintended recipient binding,
- replay or reuse,
- recipient identity mismatch,
- unclear revocation.

Future controls before any real transport:

- explicit recipient node review,
- one-time or bounded-use key policy,
- replay guard,
- receipt/audit trail,
- no key material in logs.

### radio-frequency

Planning risks:

- accidental broad discoverability,
- frequency guessing,
- stale frequency reuse,
- recommendation/feed confusion,
- central-ranking confusion.

Future controls before any real transport:

- explicit frequency intent,
- provenance review,
- visible selector policy,
- no central black-box ranking claim,
- no automatic feed update.

### mirroring

Planning risks:

- copying more than intended,
- stale mirror copies,
- sender/receiver mismatch,
- repeated fetch beyond intended count,
- conflating mirror copy with trust or acceptance.

Future controls before any real transport:

- exact block/zet scope,
- receiver node binding,
- copy count or replay guard,
- receipt/audit trail,
- explicit post-copy review before trust/import/anchor.

## Header / Body Boundary

The planner keeps the `header` / 초록 framing.

The header is a safe guide/index surface for review and AI indexing before the full `body` / 본문 is read. The would-transport plan must not output body text.

## Output Boundary

The planner returns:

- `lifecycle_action: zet_transport_would_plan`,
- `plan_status: transport_plan_preview_not_recorded`,
- `policy_reused_from: zet_shared_update_record_review_preview`,
- `would_change: []`,
- method-specific `risks`,
- method-specific `required_future_controls`,
- explicit closed flags for transport, key creation, radio-frequency access, mirroring payload creation, provider calls, queue jobs, workers, feed updates, trust, import, acceptance, attestation, signature, anchor, projection write, and receipt write.

The planner does not echo raw body text, local absolute paths, provider URLs, tokens, secrets, or private source locations.

## Non-Goals

v0.2.59 does not implement real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed updates, recommendation execution, trust, import, acceptance, attestation, signature, anchor, minting, provider sync, WordPress publishing, projection writes, projection receipts, queues, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.
