# Work Log: v0.2.20 GitHub Repository Setup Planner

Date: 2026-05-25

Branch: `codex/v0.2.20-github-repository-setup-plan`

## User Intent

Add a safe dry-run-first GitHub repository setup planner for WOM profiles.

The desired user flow is:

```text
resolve WOM profile
-> confirm target archive context
-> plan private GitHub repository metadata
-> ask human approval
-> write only local provider metadata and receipts
```

This batch must not create GitHub repositories, run OAuth, call GitHub APIs, run `gh`, run `git remote`, push, or sync.

## Decisions

- Keep WOM-kit naming from v0.2.19 unchanged.
- Add CLI `archive github-repo <archive-root> --dry-run --format json`.
- Add local-only `--approve --reviewed-by` mode for provider metadata and receipt writes.
- Add read-only MCP `github_repository_setup_plan`.
- Keep MCP free of GitHub apply/create/connect/push/sync tools.
- Use `zettel-kasten-<profile_slug>` as the default repository name.
- Require explicit ASCII profile slugs when a profile id/label cannot safely provide one.

## Implementation Notes

- Core logic lives in `wom_kit.archive_services`.
- CLI wiring lives in `wom_kit.archive_cli`.
- MCP wiring lives in `wom_kit.mcp_server`.
- Provider bindings store safe metadata only: owner, repo, visibility, remote protocol, env var names, and account refs.
- Optional local account hints are written only under ignored `profiles/local/`.

## Safety Notes

- Dry-run writes nothing.
- Approve mode writes only:
  - `provider-bindings.yml`,
  - `receipts/providers/*.github-repository-setup.json`,
  - optional `profiles/local/github-accounts.local.yml`.
- No external process, provider API, OAuth, git remote, push, or sync path was added.
- Repository names and profile slugs reject path-like, URL-like, email-like, and secret-like values.

## Verification Plan

- CLI dry-run output and no-write behavior.
- CLI approval gate requiring `--reviewed-by`.
- CLI local-only writes and strict doctor compatibility.
- MCP read-only plan and allowed-root behavior.
- Naming and privacy scans.

## Review Follow-Up

Claude reviewed the implementation and found no critical findings. The main pre-merge fix was approval atomicity: a failure while writing the receipt or optional ignored local profile must not leave `provider-bindings.yml` modified without its matching receipt.

Follow-up changes:

- Write the provider setup receipt before changing `provider-bindings.yml`.
- Snapshot and restore `provider-bindings.yml` if any later approved write fails.
- Remove the newly created receipt if approved setup cannot complete.
- Restore the optional ignored local GitHub profile hint if that path was touched before failure.
- Tighten `github_account_ref` validation so bare domains and non-`github:account:` scheme-like prefixes are blocked.
- Clarify CLI help text so `--approve` is described as a versioned metadata/receipt write, not a live GitHub operation.
- Add regression tests for unsafe owner/account refs, missing `profiles/local/` `.gitignore` protection, and rollback after local profile write failure.
