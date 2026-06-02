# ZET Shared Update Record Review Index

Date: 2026-06-02
Status: read-only dry-run preview

## Summary

v0.2.58 adds a read-only index preview for local ZET shared update record JSON files.

The index answers one narrow question:

```text
Which local shared update records in this archive-relative directory can be previewed safely before any receiver-side renewal action exists?
```

It does not record review, accept updates, refresh feeds, grant trust, import content, write attestations, create signatures, anchor anything, call providers, write receipts, publish projections, or run ZET transport.

v0.2.59 adds [ZET Transport Threat Model](zet-transport-threat-model.md) planning for one selected shared update record after the single-record review policy passes. That planner still writes nothing and opens no real transport.

## CLI

```powershell
python wom-kit\cli\archive.py shared-update-record-review-index <archive-root> --records-dir <archive-relative-dir> --dry-run --format json
```

The `--records-dir` path must be archive-relative and contained under the archive root. Absolute paths, URL-like paths, traversal, UNC paths, and NUL bytes are rejected.

The command scans only direct-child `.json` files under the selected directory. It ignores non-JSON files, does not recurse, sorts output deterministically by archive-relative path, and uses a conservative default limit of `100`.

## MCP

The MCP tool is:

```text
zet_shared_update_record_review_index
```

MCP accepts only `dry_run: true` as a JSON boolean. String values such as `"true"` are rejected.

MCP does not expose write/apply/publish/transport/import/trust/attest/sign/anchor sibling tools for shared update record indexes.

## Policy Reuse

The index intentionally reuses the v0.2.56 single-record review preview policy for each JSON record.

That means each record is still treated as untrusted input and is blocked if it includes body text, unsafe local/private/provider values, archive mismatch, or any true mutation/write/transport/provider/trust/import/acceptance/attestation/signature/mint/anchor/apply/feed/recommendation flag.

The index does not maintain a separate policy list. This keeps the multi-record surface aligned with the one-record preview.

## Output Boundary

The index returns:

- `lifecycle_action: zet_shared_update_record_review_index`,
- `index_status: index_preview_not_recorded`,
- `would_change: []`,
- `policy_reused_from: zet_shared_update_record_review_preview`,
- compact per-record entries with path, status, record kind/version, blocker count, warning count, and sanitized refs when available,
- explicit closed flags for review index recording, review recording, feed update, trust, import, acceptance, attestation, signature, anchor, real ZET transport, provider calls, projection writes, and receipt writes.

The index does not echo raw body text, local absolute paths, provider URLs, tokens, secrets, or private source locations.

## Safe Order

```text
receive local records -> review index -> review one selected record -> future human approval -> future renewal path
```

## Non-Goals

v0.2.58 does not implement shared-update review writes, shared-update transport, receiver-side renewal writes, neighbor feed updates, trust, import, acceptance, attestation, signature, anchor, minting, provider sync, WordPress publishing, projection writes, projection receipts, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.
