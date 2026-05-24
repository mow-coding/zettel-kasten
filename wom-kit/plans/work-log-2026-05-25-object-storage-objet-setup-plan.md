# Work Log: v0.2.21 Object Storage / Objet Setup Planner

Date: 2026-05-25

Branch: `codex/v0.2.21-object-storage-objet-setup-plan`

## User Intent

Add a safe dry-run-first setup planner for WOM profile objet storage.

The desired user flow is:

```text
resolve WOM profile
-> confirm target archive context
-> plan private objet storage metadata
-> ask human approval
-> write only local provider metadata and receipts
```

This batch must not create buckets, run OAuth, call provider APIs, upload, sync, copy source files, hash files, or import source content.

## Decisions

- Keep WOM-kit naming from v0.2.19 unchanged.
- Use `objet` as WOM product language for source/original objects stored outside Git.
- Keep `object storage` as the technical provider/API term.
- Add CLI `archive object-storage <archive-root> --dry-run --format json`.
- Add local-only `--approve --reviewed-by` mode for provider metadata and receipt writes.
- Add read-only MCP `object_storage_setup_plan`.
- Keep MCP free of object storage apply/create/connect/upload/sync tools.
- Use `zettel-kasten-<normalized-profile-slug>-objets` as the default bucket/container name.
- Use `archives/<archive_id>/objets/` as the default prefix.
- Require explicit ASCII profile slugs when a profile id/label cannot safely provide one.

## Implementation Notes

- Core logic lives in `wom_kit.archive_services`.
- CLI wiring lives in `wom_kit.archive_cli`.
- MCP wiring lives in `wom_kit.mcp_server`.
- Provider bindings store safe metadata only: provider kind, bucket/container name, prefix, visibility, region, endpoint ref, env var name, and account ref.
- Optional local account hints are written only under ignored `profiles/local/`.
- Approved writes are rollback-safe so `provider-bindings.yml` is not left modified without its matching receipt.

## Safety Notes

- Dry-run writes nothing.
- Approve mode writes only:
  - `provider-bindings.yml`,
  - `receipts/providers/*.object-storage-setup.json`,
  - optional `profiles/local/object-storage-accounts.local.yml`.
- No external process, provider API, OAuth, bucket creation, upload, sync, copy, hashing, or source import path was added.
- Bucket names, profile slugs, account refs, endpoint refs, and region labels reject path-like, URL-like, email-like, and secret-like values.

## Verification Plan

- CLI dry-run output and no-write behavior.
- CLI approval gate requiring `--reviewed-by`.
- CLI local-only writes and strict doctor compatibility.
- CLI rollback after optional local profile write failure.
- MCP read-only plan and allowed-root behavior.
- v0.2.20 GitHub repository setup tests continue passing.
- Naming and privacy scans.

## Review Follow-Up

Claude reviewed the implementation and found no critical findings. The main design question was local profile multiplicity: whether one WOM profile can preserve multiple object-storage buckets.

Decision:

```text
One WOM profile may preserve multiple object-storage buckets.
```

Follow-up changes:

- Match local object-storage profile hints by `provider_kind + bucket_name`, not by profile id alone.
- Keep local profile behavior aligned with `provider-bindings.yml`, where object-storage bindings are keyed by provider kind and bucket.
- Add a regression test that approves two buckets for the same profile and confirms both the versioned provider bindings and ignored local profile hints preserve both buckets.
- Add explicit tests that unsafe endpoint refs such as raw URLs, `s3://...`, bare domains, and arbitrary scheme-like strings are blocked.
