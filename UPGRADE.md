# Upgrade Guide

[한국어 업그레이드 가이드](UPGRADE.ko.md)

This guide explains how to move between public `zettel-kasten` / `zet` versions.

The project is versioned because archive rules, zettel metadata, object manifests, provenance records, and future `ZET` sharing envelopes must be understandable across users and tools.

## Quick Rule

```text
PATCH upgrade -> documentation, validation, or compatible fixes
MINOR upgrade -> compatible new features or optional fields
MAJOR upgrade -> breaking protocol/schema changes
```

Before upgrading a real archive:

1. Read the target version note in `wom-kit/docs/releases/`.
2. Back up the private archive repository and object manifests.
3. Run `archive doctor --strict`.
4. Run migration commands in dry-run mode first when available.
5. Commit private archive changes only after reviewing generated receipts.

The archive should never silently rewrite memory.

## Public Versions

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.2.24` | current public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
| `v0.2.23` | superseded public pre-release | `wom-kit/docs/releases/v0.2.23.md` |
| `v0.2.22` | superseded public pre-release | `wom-kit/docs/releases/v0.2.22.md` |
| `v0.2.21` | superseded public pre-release | `wom-kit/docs/releases/v0.2.21.md` |
| `v0.2.20` | superseded public pre-release | `wom-kit/docs/releases/v0.2.20.md` |
| `v0.2.19` | superseded public pre-release | `wom-kit/docs/releases/v0.2.19.md` |
| `v0.2.18` | superseded public pre-release | `wom-kit/docs/releases/v0.2.18.md` |
| `v0.2.17` | superseded public pre-release | `wom-kit/docs/releases/v0.2.17.md` |
| `v0.2.16` | superseded public pre-release | `wom-kit/docs/releases/v0.2.16.md` |
| `v0.2.15` | superseded public pre-release | `wom-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `wom-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `wom-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `wom-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `wom-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `wom-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `wom-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `wom-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `wom-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `wom-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `wom-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `wom-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `wom-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `wom-kit/docs/releases/v0.2.2.md` |

## From `v0.2.23` To `v0.2.24`

This is a compatible block header preview patch.

What changed:

- added `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- added `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- added read-only header derivation for `block = zet + header`,
- added deterministic body, header, and block hash previews,
- added read-only MCP `block_header_check`.

No private archive migration is required.

This release does not modify zets, mint, write receipts, read referenced objet/source file bodies, calculate referenced source hashes, follow provider URLs, call provider APIs, or implement transport/economic layers.

Safe conceptual order:

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## From `v0.2.22` To `v0.2.23`

This is a compatible source intake draft composer patch.

What changed:

- added `archive create-draft --source-intake-plan <json-file>`,
- validated that consumed source intake plans are successful dry-runs, blocker-free, metadata-only, and safe,
- merged `source_refs_for_draft` into draft `source_refs` while preserving explicit `--source-ref` values,
- added optional draft `source_intake` metadata with a plan hash and content access proof,
- added MCP `create_draft_zettel` support for structured `source_intake_plan` objects.

No private archive migration is required.

This release does not read original source files from the plan, follow local paths inside the plan, apply source intake, capture objets, copy, upload, import, OCR, transcribe, calculate full source hashes, call provider APIs, automatically mint, or add MCP real minting.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json > source-intake-plan.json

archive create-draft <archive-root> --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

## From `v0.2.21` To `v0.2.22`

This is a compatible source intake planner patch.

What changed:

- added `archive source-intake <archive-root> --dry-run --format json`,
- added metadata-only locator planning for local files, source map items, source-relative paths, manifested objets, provider refs, and AI artifacts,
- added draft-ready `source_refs_for_draft` so AI runtimes can feed safe refs into `create-draft --dry-run`,
- added object storage context reporting from `provider-bindings.yml`,
- added read-only MCP `source_intake_plan`.

No private archive migration is required.

This release does not read file bodies, calculate full hashes, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts automatically, mint, or sync providers.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json
```

## From `v0.2.20` To `v0.2.21`

This is a compatible object storage/objet setup planner patch.

What changed:

- added `archive object-storage <archive-root> --dry-run --format json`,
- added safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- added default objet prefix planning as `archives/<archive_id>/objets/`,
- added strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- added `--approve --reviewed-by` for local-only provider metadata and setup receipt writes,
- added optional ignored local object storage account hints with `--write-local-profile`,
- added read-only MCP `object_storage_setup_plan`.

No private archive migration is required.

This release does not create buckets, run OAuth, call provider APIs, upload, sync, copy source files, hash files, or import source content.

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --storage-account-ref storage:account:honggildong \
  --format json
```

## From `v0.2.19` To `v0.2.20`

This is a compatible GitHub profile repository setup planner patch.

What changed:

- added `archive github-repo <archive-root> --dry-run --format json`,
- added safe default repository names as `zettel-kasten-<profile_slug>`,
- added strict safety gates for profile slugs, repository names, GitHub owners, and account references,
- added `--approve --reviewed-by` for local-only provider metadata and setup receipt writes,
- added optional ignored local account hints with `--write-local-profile`,
- added read-only MCP `github_repository_setup_plan`.

No private archive migration is required.

This release does not create GitHub repositories, run OAuth, call GitHub APIs, run `gh`, configure git remotes, push, or sync.

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

## From `v0.2.18` To `v0.2.19`

This is a compatible WOM-kit naming and path cleanup patch.

What changed:

- the implementation folder is now `wom-kit/`,
- the Python import package is now `wom_kit`,
- package metadata now uses the project name `wom-kit`,
- `archive` and `archive-mcp` remain available as compatibility console scripts,
- preferred aliases `wom` and `wom-mcp` are available when installed from the package metadata.

No private archive migration is required.

Current commands should use the new paths:

```bash
python wom-kit/cli/archive.py doctor wom-kit/examples/fake-life-archive --strict
python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

## From `v0.2.17` To `v0.2.18`

This is a compatible profile-aware draft zet creation dry-run patch.

What changed:

- added `archive create-draft --dry-run --format json`,
- added replay-safe draft creation fields for draft id, created-at timestamp, expected body hash, and draft approver,
- added profile-aware provenance fields for resolved profile id, operator id, authority mode, source refs, local AI sessions, assisting actors, and supervising actors,
- extended MCP `create_draft_zettel` with the same dry-run and profile-aware inputs,
- kept real draft writes constrained to `inbox/`,
- kept minting separate through `mint-zet --approve --reviewed-by`.

No private archive migration is required. Existing drafts remain valid.

For profile-bound AI writes, first run profile resolution and runtime context, then dry-run draft creation. After human draft approval, replay the same draft id, created-at timestamp, expected archive id/type, profile id, and expected body hash.

```bash
git fetch --tags
git checkout v0.2.18
```

## From `v0.2.16` To `v0.2.17`

This is a compatible WOM Profile Registry dry-run patch.

What changed:

- added `archive profile-list --registry <path> --format json`,
- added `archive profile-resolve --registry <path> --target <query> --format json`,
- added read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- added token-state aware profile resolution before runtime context and draft work,
- added an example registry template at `wom-kit/templates/profiles/wom-profiles.example.yml`.

No private archive migration is required.

This release does not add profile registration, token storage, create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

```bash
git fetch --tags
git checkout v0.2.17
```

## From `v0.2.15` To `v0.2.16`

This is a compatible WOM AI Runtime Context Layer patch.

What changed:

- added `archive runtime-context <archive-root> --format json`,
- added `--expected-archive-id`, `--expected-type`, and `--strict` checks so terminal-capable AI runtimes can confirm they are operating on the intended archive before creating drafts, running dry-runs, or asking for mint approval,
- added default local path redaction; JSON paths are archive-relative unless `--no-redact-local-paths` is explicitly used for trusted local debugging,
- added read-only MCP tool `archive_runtime_context` with existing MCP allowed-root enforcement.

No private archive migration is required.

This release does not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP apply tool.

```bash
git fetch --tags
git checkout v0.2.16
```

## From `v0.2.14` To `v0.2.15`

This is a compatible WOM Safe HTML Profile validator dry-run patch.

What changed:

- added `archive check-safe-html --path <zet> --dry-run` as a read-only CLI command that previews whether a v0.2 Markdown-compatible zet is compatible with a future WOM Safe HTML Profile migration,
- the validator blocks zet bodies that contain `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, or inline event handler attributes such as `onclick=`,
- the validator returns structured JSON with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, a profile allowlist, a UI, live sharing, P2P transport, or external provider sync. Existing Markdown-compatible zets remain valid.

```bash
git fetch --tags
git checkout v0.2.15
```

## From `v0.2.13` To `v0.2.14`

This is a compatible documentation/spec baseline patch for the WOM Safe HTML Profile.

What changed:

- documented the distinction between `WOM`, `zet`, and `ZET`,
- clarified that `zet` is the unit document minted inside a zettel-kasten,
- clarified that `ZET` is the future communication layer that can become messenger, SNS/feed, or collaboration,
- documented WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- kept Markdown as the v0.2 authoring/import compatibility format.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, or external provider sync.

```bash
git fetch --tags
git checkout v0.2.14
```

## From `v0.2.12` To `v0.2.13`

This is a compatible WOM naming baseline and CLI alias patch.

What changed:

- documented `WOM` as the umbrella name and `Widesider of Modernity` as its expansion,
- added `archive mint-zet` as the preferred command name for minting a zet,
- kept `archive mint-zettel` as a compatibility alias,
- added `archive parcel` as the preferred command name for creating a bounded portable unit,
- kept `archive pack` as a compatibility alias,
- added `archive admit --dry-run` as the preferred command name for previewing parcel/workpack admission,
- kept `archive import --dry-run` as a compatibility alias.

No private archive migration is required.

Existing scripts can keep using the old names, but new user-facing docs should prefer `mint-zet`, `parcel`, and `admit`.

```bash
git fetch --tags
git checkout v0.2.13
```

## From `v0.2.11` To `v0.2.12`

This is a compatible real delegate receipt write patch.

What changed:

- added `archive delegate-zet --approve --reviewed-by <actor>`,
- real delegate writes create `receipts/delegate/*.delegate.json`,
- `archive doctor` validates applied delegate receipts,
- real delegate capability receipts get a generated nonce,
- claim/spent/revocation registries remain explicitly unimplemented.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.12
```

## From `v0.2.10` To `v0.2.11`

This is a compatible delegate capability contract patch.

What changed:

- added `--target-policy counterparty_bound|claimable_once` to `archive delegate-zet --dry-run`,
- made `--target-archive` optional for `claimable_once` delegate previews,
- added `delegation_capability`, `claim_binding`, and `settlement_condition` preview fields,
- kept settlement non-financial with `mode: "none"`,
- kept real P2P, claim registry, spent registry, revocation, blockchain, and payment unavailable.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.11
```

## From `v0.2.9` To `v0.2.10`

This is a compatible dry-run lifecycle feature patch.

What changed:

- added `archive delegate-zet --dry-run`,
- added `archive attest-zet --dry-run`,
- added `archive anchor-zet --dry-run`,
- added read-only MCP checks for delegate, attest, and anchor,
- added schemas for delegate receipts, attestation receipts, and anchor metadata.

No private archive migration is required.

Real P2P, feed, transport, external sending, and foreign zet import remain unavailable.

```bash
git fetch --tags
git checkout v0.2.10
```

## From `v0.2.8` To `v0.2.9`

This is a compatible terminology stabilization patch.

What changed:

- new archives default to `human_minting`,
- existing `human_promotion` archives remain valid,
- `minting_rules` may be used in zettel rules,
- `promotion_rules` remains available as the v0.2 legacy fallback,
- user-facing docs now prefer minting language.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.9
```

## From `v0.2.7` To `v0.2.8`

This is a compatible minting lifecycle feature patch.

What changed:

- added `archive mint-zettel --dry-run`,
- added `archive mint-zettel --approve --reviewed-by <id>`,
- added mint receipts under `receipts/mint/`,
- added draft snapshots under `receipts/mint/drafts/`,
- added canonical zettel `mint` frontmatter,
- added doctor validation for mint receipts and SHA-256 file links,
- added read-only MCP `mint_zettel_check`.

No private archive migration is required.

If you mint new zettels, keep the generated canonical zettel, mint receipt, and draft snapshot together.

```bash
git fetch --tags
git checkout v0.2.8
```

## From `v0.2.3` To `v0.2.4`

This is a documentation polish patch.

What changed:

- rewrote `README.md` as a cleaner English project entrypoint,
- added `README.ko.md` as a full Korean entrypoint,
- split upgrade documentation into English and Korean files,
- clarified the public positioning, current status, privacy boundary, storage model, and text provenance.

No private archive migration is required.

Recommended steps:

```bash
git fetch --tags
git checkout v0.2.4
```

## From `v0.2.2` To `v0.2.3`

This is a bilingual documentation patch.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.3
```

## From `v0.2.1` To `v0.2.2`

This is a documentation, provenance, and public-history hygiene patch.

No private archive migration is required.

Important concept change:

```text
original editable text != OCR/AI-derived text
```

Both should be stored, but OCR/AI-derived text should keep derivation metadata and review status.

## Staying On An Older Version

Users may stay on an older version.

That is part of the design:

```text
old version -> old rule set
new version -> updated rule set
```

Future sharing and collaboration features should make the sender/receiver version explicit.

## Future Release Requirements

Every future public release should include:

- changelog entry,
- release note under `wom-kit/docs/releases/`,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
