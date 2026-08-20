# Approval Handoff Audit

Status: v0.4.0 read-only legacy-unbound advisory audit

WOM now has a read-only audit command for approval handoff records.

This structurally checks a previously written legacy handoff record. A match is
classified `legacy_unbound` and advisory only. It always returns
`future_operation_authorized: false` and cannot authorize a future operation.
The audit does not consume the record, execute an operation, read private
material, or call any provider.

## Command

```powershell
archive approval-handoff-audit <archive-root> `
  --handoff-record ops/approval-handoffs/<handoff-id>.yml `
  --expected-operation-kind read_private_material `
  --expected-status approved_once `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive handoff-audit <archive-root> ...
archive human-approval-handoff-audit <archive-root> ...
```

## What It Checks

- The record path stays under `ops/approval-handoffs/`.
- The record schema is `wom-kit/approval-handoff/v0.1`.
- The record status matches `--expected-status`.
- The record operation kind matches `--expected-operation-kind` when provided.
- `approved_once` records include `reviewed_by`.
- The record itself does not claim operation execution, private material reads,
  or provider calls.

## Output Boundary

The audit may report safe metadata such as:

- handoff id,
- record path,
- status,
- operation kind,
- whether target/action fields are present,
- `future_operation_authorized: false`, with the legacy-unbound/advisory
  classification.

It deliberately does not echo target ref values or requested action values.

## Safety Boundary

The command:

- reads only the handoff metadata record,
- reads no private material,
- calls no providers,
- checks no network,
- executes no operation,
- echoes no target ref values,
- echoes no requested action values,
- echoes no local absolute paths, tokens, or secret values,
- writes nothing.

Even an `approved_once` record with matching metadata grants no current write,
credential, provider, publication, or private-read authority.

## Still Future

- Matching approval handoffs to target metadata hashes.
- Stale approval detection when target metadata changes.
- Command-specific enforcement for live fetch, write, publish, and credential
  operations.
