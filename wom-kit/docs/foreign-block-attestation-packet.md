# Foreign Block Attestation Packet Preview

Status: v0.2.41 compatible baseline

## Principle

```text
Foreign blocks stay untrusted.
An attestation packet preview is not an attestation.
Human or policy approval must happen in a later explicit step.
```

## Purpose

`foreign-block-attestation` is the read-only step after `foreign-block-trust`.

It consumes a v0.2.29+ `foreign_block_trust_preview` report and prepares a human-review packet preview. The packet is meant to help a future reviewer see what would need to be checked before any real attestation path exists.

It does not read the original foreign artifact again.

## CLI

```bash
archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json
archive foreign-block-attestation <archive-root> --stdin --dry-run --format json
```

Optional context:

```bash
--prospective-attestor person:reviewer
--review-scope human_review
```

`prospective_attestor` is preview metadata only. It is not approval and not a signature.

## Output Boundary

The output keeps:

- `trust_state: untrusted_foreign`,
- `attestation_packet_preview.would_attest: false`,
- `attestation_packet_preview.attestation_status: not_created`,
- `would_change: []`.

The `packet_status` can be:

- `blocked`,
- `manual_review_required`,
- `ready_for_human_attestation_review`.

`ready_for_human_attestation_review` is not trust, not approval, and not an attestation. It only means the trust report is clean enough to present to a future human or policy review step.

## Quarantine Plan And Write

v0.2.31 adds the next read-only step:

```bash
archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json
archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json
```

`foreign-block-quarantine` consumes this packet preview and proposes where a future isolated review copy could live under `quarantine/foreign-blocks/<case-id>/...`. It does not create those paths.

`ready_for_future_quarantine_write` is not trust, not import, not quarantine, and not approval.

v0.2.32 adds the first CLI-only approved isolation write:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json
```

Approved mode writes only a sanitized quarantine case and quarantine write receipt. It keeps `trust_state: untrusted_foreign` and still does not trust, import, mint, attest, anchor, delegate, sign, execute, or accept the foreign block.

v0.2.33 adds a read-only review index for those existing quarantine cases:

```bash
archive quarantine-review <archive-root> --format json
```

The index helps a reviewer inventory untrusted quarantine cases and receipt consistency. It does not create trust, import, attestation, receipt writes, mint outputs, anchors, delegation, signatures, or acceptance.

v0.2.34 adds a read-only decision preview for one existing quarantine case:

```bash
archive quarantine-decision <archive-root> --case-id case-review-001 --dry-run --format json
```

The preview proposes a candidate future decision path only. It records no decision and still does not create trust, import, attestation, receipt writes, mint outputs, anchors, delegation, signatures, or acceptance.

v0.2.38 adds a later read-only candidate planner after an approved local decision has been recorded as `eligible_for_attestation_review`:

```bash
archive attestation-review-candidate <archive-root> --case-id case-review-001 --dry-run --format json
```

That candidate plan is not an attestation. It re-reads the sanitized quarantine case, quarantine receipt, decision record, and decision receipt, then prepares safe human-review metadata only.

v0.2.39 adds a separate CLI-only record step for a valid candidate plan:

```bash
archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json
```

Approved mode writes only an untrusted candidate record and matching receipt. It still creates no trust, import, attestation, signature, mint, sharing, provider call, or ZET transport.

v0.2.40 adds a read-only index for recorded candidate records:

```bash
archive attestation-candidate-review <archive-root> --format json
```

The index validates recorded candidates, candidate receipts, and upstream quarantine/decision state. It writes nothing and still creates no trust, import, attestation, signature, mint, sharing, provider call, acceptance, apply behavior, or ZET transport.

v0.2.41 adds a read-only non-binding statement draft preview for one recorded candidate:

```bash
archive attestation-statement-draft <archive-root> --case-id case-review-001 --dry-run --format json
```

The draft preview is not an attestation and creates no trust, import, signature, mint, receipt, sharing, provider call, acceptance, apply behavior, or ZET transport.

## Safety Checks

The command blocks if the trust report:

- is not a successful dry-run `foreign_block_trust_preview`,
- does not keep `trust_state: untrusted_foreign`,
- has blockers or non-empty `would_change`,
- claims an attestation was created,
- claims hashes are verified or trusted,
- contains unsafe local paths, provider URLs, token-like strings, or secret-like values.

## MCP

```text
foreign_block_attestation_packet_check
```

The MCP tool is read-only and dry-run only. It accepts a structured trust report object or an archive-relative trust report path.

## Non-Goals

v0.2.41 does not implement:

- quarantine decision apply,
- attestation review candidate apply or acceptance,
- attestation statement writes,
- real trust/apply/import,
- attestation writes,
- foreign attestation writes,
- quarantine review apply or acceptance,
- minting,
- anchoring,
- delegation,
- real ZET transport,
- signing,
- payment,
- staking,
- consensus,
- blockchain,
- wallet key management,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.
