# Archive Identity Spec v0.1

An archive identity document names the archive, its owner, its operators, its public keys, trusted counterparties, and lineage hints.

It lives at:

```text
archive-identity.yml
```

## Purpose

`archive.yml` says what the archive is.

`archive-identity.yml` says who the archive belongs to, who is allowed to operate it, and which other archives or people it already trusts.

This is the first trust-gate layer for sharing, importing, merging, forking, and exit workflows.

## Minimal Shape

```yaml
identity:
  archive_id: archive:personal:example
  identity_id: identity:archive:personal:example
  scope: personal
  principal_id: person:example
  display_name: Example Person
  public_keys:
    - key_id: key:example:primary
      algorithm: ssh-ed25519
      fingerprint: SHA256:example
      status: active
ownership:
  owner_id: person:example
  owner_kind: person
  owner_display_name: Example Person
  owner_archive_id: archive:personal:example
  operators:
    - operator_id: person:example
      role: owner_operator
      permissions:
        - capture
        - curate
        - approve
        - transfer_request
  subjects: []
  transfer_policy:
    ownership_transfer_allowed: true
    requires_human_approval: true
    requires_receipt: true
    receipt_action: transfer_archive_ownership
    default_transfer_target:
trusted_counterparties:
  - identity_id: identity:archive:company:example
    archive_id: archive:company:example
    principal_id: company:example
    expected_fingerprint: SHA256:example-company
    trust_level: out_of_band_verified
lineage:
  parents: []
  children: []
  forked_from:
  merged_from: []
  exited_from:
```

## Owner, Operator, Subject

The archive owner and the people operating the archive are different concepts.

```text
owner
  The person or group that the archive belongs to.

operator
  A person or role allowed to write, curate, approve, or request transfers.

subject
  A person the records are about, even if that person is not yet the owner.
```

For example, a child archive may start with:

```yaml
ownership:
  owner_id: family:example-household
  owner_kind: family
  operators:
    - operator_id: person:father
      role: parent_operator
    - operator_id: person:mother
      role: parent_operator
  subjects:
    - subject_id: person:child
      relationship: child_subject
  transfer_policy:
    ownership_transfer_allowed: true
    requires_human_approval: true
    requires_receipt: true
    receipt_action: transfer_archive_ownership
    default_transfer_target: person:child
```

This means the household owns and operates the archive while the child is young. Later, ownership can be transferred to the child through a receipt-backed event.

The first transfer path supports preview and CLI-only local apply:

```text
archive transfer-ownership <archive> \
  --new-owner person:child \
  --operator-after person:child \
  --approved-by person:father \
  --approved-by person:mother \
  --counterparty-id person:child \
  --counterparty-fingerprint SHA256:child \
  --dry-run
```

This returns `scope_gate`, `trust_gate`, `ownership_gate`, `provider_change_plan`, and `receipt_preview`. It does not write the receipt and does not change the owner.

Real local transfer requires explicit approval:

```text
archive transfer-ownership <archive> \
  --new-owner person:child \
  --operator-after person:child \
  --approved-by person:father \
  --counterparty-id person:child \
  --counterparty-fingerprint SHA256:child \
  --approve \
  --reviewed-by person:father
```

This updates the archive-internal owner/operator model, appends `lineage.ownership_transfers`, and writes a `dry_run:false` receipt. It does not mutate external provider accounts.

The receipt preview follows `schemas/ownership-transfer-receipt.schema.json`. Example receipts can live under `receipts/lineage/*.ownership-transfer.json` and are validated by `archive doctor`.

## Trust Rule

Archive sharing must not trust a name alone.

The receiver should verify:

```text
counterparty id
expected public key fingerprint
out-of-band confirmation when risk is high
```

In v0.1, the CLI checks `trusted_counterparties[].expected_fingerprint`.

Future versions may add signed workpacks, signed receipts, and key rotation receipts.

