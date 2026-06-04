# Shared Update Route Preview

Date: 2026-06-04
Status: read-only dry-run preview
Version: v0.3.1

## Summary

`shared-update-route-preview` is a thin read-only router for one local shared
update record.

It answers one narrow question:

```text
After the shared update record passes the existing metadata-only review gate,
which receiver-side route could a human consider next: delegate, attest, anchor,
or none?
```

The command does not perform that route. It points to the existing canonical
surface and writes nothing.

## CLI

```powershell
python wom-kit\cli\archive.py shared-update-route-preview <archive-root> --record <archive-relative-json> --dry-run --format json
```

The `--record` path must be archive-relative and contained under the archive
root. Absolute paths, URL-like paths, traversal, UNC paths, and NUL bytes are
rejected by the reused shared-update record review policy.

## Route Pointers

The output includes pointer fields only:

- `route_eligibility.delegate` / `delegate_route_preview` points to `delegate-zet`.
- `route_eligibility.attest` / `attest_route_preview` points to `attest-zet`.
  It also names `shared-update-attestation-review` as the related shared-update
  review command and returns the required flags `--approve` and `--reviewed-by`.
- `route_eligibility.anchor` / `anchor_route_preview` points to `anchor-zet`.
- `route_eligibility.none` / `none_route_preview` applies when the metadata is blocked or does not map to a
  known route.

These fields are route-eligibility pointers, not full lifecycle previews. The
command does not duplicate the logic of `delegate-zet`, `attest-zet`, or
`anchor-zet`.

Naming a route command does not grant permission to run it. Write-capable
surfaces still pass a separate human-approval gate. For example,
`shared-update-attestation-review` still requires `--approve` and
`--reviewed-by`. This route preview only names the next surface; it does not
authorize it.

## Output Boundary

The route preview returns:

- `lifecycle_action: zet_shared_update_route_preview`,
- `route_status: route_preview_not_recorded`,
- `candidate_route: delegate | attest | anchor | none`,
- `source_shared_update_record.record_path`,
- `source_shared_update_record.sha256`,
- `related_shared_update_review_required_flags: ["--approve", "--reviewed-by"]`
  on the attestation/review route pointer,
- `trust_state: untrusted_foreign`,
- `attestation_status: not_created`,
- `signature_status: not_created`,
- `anchor_status: not_created`,
- `renewal_status: not_performed`,
- `would_change: []`,
- explicit closed flags for write, transport, trust, import, acceptance,
  attestation, signature, anchor, apply, provider, projection, queue, worker,
  blockchain, token, model-training, backpropagation, and full-auto behavior.

The preview does not echo raw body text, local absolute paths, provider URLs,
tokens, secrets, or private source locations.

## Route Selection

The router uses only the sanitized `receiver_review_preview.proposed_action`
metadata exposed by `shared-update-record-review`. Free-form action text is not
echoed; only recognized route tokens are carried into this preview.

Conservative mapping:

- metadata mentioning a delegate route maps to `delegate`,
- metadata mentioning an anchor route maps to `anchor`,
- `review_before_renewal` or attestation/review metadata maps to `attest`,
- unknown or blocked metadata maps to `none`.

`anchor` means only that an anchor route could be considered later. It does not
mean the shared update was anchored, applied, trusted, imported, or accepted.

## MCP

v0.3.1 adds no MCP write/apply tool for this route preview. MCP remains closed
for shared-update write/apply/import/trust/anchor behavior.

## Non-Goals

This preview does not implement real ZET transport, key creation, key-sharing
registry, radio-frequency access, mirroring delivery, neighbor feed update,
automatic renewal, trust graph mutation, import, acceptance, real attestation,
signature, anchor, apply, public proof, provider sync, WordPress publishing,
projection write, receipt write, queues, workers, DID/wallet/key custody,
payments, staking, consensus, blockchain, token, system token, governance,
model training, backpropagation, or full-auto behavior.
