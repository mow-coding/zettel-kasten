# ZET Shared Update Record Review Preview

Date: 2026-06-02
Status: read-only dry-run preview

## Summary

v0.2.56 adds a read-only review preview for one local ZET shared update record JSON before any receiver-side renewal action exists.

The preview answers one narrow question:

```text
Can this local shared update review record be inspected safely, without treating it as trust, import, acceptance, attestation, signature, feed update, projection, or real ZET transport?
```

## CLI

```powershell
python wom-kit\cli\archive.py shared-update-record-review <archive-root> --record <archive-relative-json> --dry-run --format json
```

The `--record` path must be archive-relative and contained under the archive root. Absolute paths, URL-like paths, traversal, UNC paths, and NUL bytes are rejected.

## MCP

The MCP tool is:

```text
zet_shared_update_record_review_preview
```

MCP accepts only `dry_run: true` as a JSON boolean. String values such as `"true"` are rejected.

MCP does not expose write/apply/publish/transport/import/trust/attest/sign/anchor sibling tools for shared update records.

## Output Boundary

The preview returns:

- `lifecycle_action: zet_shared_update_record_review_preview`,
- `preview_status: preview_not_recorded`,
- `trust_state: untrusted_foreign`,
- `would_change: []`,
- explicit closed flags for feed update, trust, import, acceptance, attestation, signature, anchor, real ZET transport, provider calls, projection writes, and receipt writes.

The preview does not echo raw body text, local absolute paths, provider URLs, tokens, secrets, or private source locations.

## Validation

The selected JSON record is treated as untrusted input.

The preview blocks if:

- the record path is unsafe or outside the archive,
- the JSON is not an object,
- the record does not claim `dry_run: true`,
- the record claims `body_included: true`,
- body-like fields are present,
- a mutation/write/transport/provider/trust/import/acceptance/attestation/signature/mint/anchor/apply/feed/recommendation flag is `true`,
- private location, provider URL, token-like, or secret-like values appear,
- a record-level `archive_id` conflicts with the current archive.

## Non-Goals

v0.2.56 does not implement shared-update transport, receiver-side renewal writes, neighbor feed updates, trust, import, acceptance, attestation, signature, anchor, minting, provider sync, WordPress publishing, projection writes, projection receipts, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

The safe order remains:

```text
receive local record -> review preview -> future human approval -> future renewal path
```
