# Work Log: v0.2.11 Delegate Capability Contract

Date: 2026-05-23
Status: public-safe work log
Related release: v0.2.11

## Context

`v0.2.10` introduced dry-run `delegate-zet`, `attest-zet`, and `anchor-zet` previews.

After that, the project clarified that `delegate` must not mean a reusable public link. A delegated `zet` should be represented as a capability that is either bound to a known counterparty or claimable once and later bound through attestation.

## Work Performed

Implemented the dry-run contract for:

- `counterparty_bound` delegation,
- `claimable_once` delegation,
- attestation-time claim binding,
- anchor-time claim provenance preservation,
- explicit non-financial settlement default.

The new contract is still preview-only. It does not write real delegate receipts, maintain a claim registry, mark capabilities spent, send data over a network, or perform payment/blockchain settlement.

## Behavior

`delegate-zet --dry-run` now accepts:

```text
--target-policy counterparty_bound
--target-policy claimable_once
```

`counterparty_bound` keeps the existing trust gate behavior and requires `--target-archive`.

`claimable_once` can run without `--target-archive`, `--counterparty-id`, or `--counterparty-fingerprint`. Its recipient trust gate is deferred until attestation.

Delegate previews now include:

- `delegation_capability`,
- capability id,
- claim/spent preview states,
- nonce placeholder,
- binding method,
- `settlement_condition: {mode: "none"}`.

Attestation previews now include `claim_binding`.

Anchor metadata previews preserve `claim_binding` provenance.

## Verification

The implementation was verified with focused CLI and MCP tests before full validation.

Full validation was also run:

```bash
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

Result:

```text
142 tests OK, 8 skipped
doctor strict: 0 errors, 0 warnings
```

## Follow-Up

Future batches can design real capability writes, claim receipts, spent registries, revocation, workpack transport, or optional settlement layers.

Those features should remain separate from this dry-run contract so the local archive does not accidentally become a public-link sharing system.
