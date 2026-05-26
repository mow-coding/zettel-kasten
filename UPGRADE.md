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
| `v0.2.43` | current public pre-release | `wom-kit/docs/releases/v0.2.43.md` |
| `v0.2.42` | superseded public pre-release | `wom-kit/docs/releases/v0.2.42.md` |
| `v0.2.41` | superseded public pre-release | `wom-kit/docs/releases/v0.2.41.md` |
| `v0.2.40` | superseded public pre-release | `wom-kit/docs/releases/v0.2.40.md` |
| `v0.2.39` | superseded public pre-release | `wom-kit/docs/releases/v0.2.39.md` |
| `v0.2.38` | superseded public pre-release | `wom-kit/docs/releases/v0.2.38.md` |
| `v0.2.37` | superseded public pre-release | `wom-kit/docs/releases/v0.2.37.md` |
| `v0.2.36` | superseded public pre-release | `wom-kit/docs/releases/v0.2.36.md` |
| `v0.2.35` | superseded public pre-release | `wom-kit/docs/releases/v0.2.35.md` |
| `v0.2.34` | superseded public pre-release | `wom-kit/docs/releases/v0.2.34.md` |
| `v0.2.33` | superseded public pre-release | `wom-kit/docs/releases/v0.2.33.md` |
| `v0.2.32` | superseded public pre-release | `wom-kit/docs/releases/v0.2.32.md` |
| `v0.2.31` | superseded public pre-release | `wom-kit/docs/releases/v0.2.31.md` |
| `v0.2.30` | superseded public pre-release | `wom-kit/docs/releases/v0.2.30.md` |
| `v0.2.29` | superseded public pre-release | `wom-kit/docs/releases/v0.2.29.md` |
| `v0.2.28` | superseded public pre-release | `wom-kit/docs/releases/v0.2.28.md` |
| `v0.2.27` | superseded public pre-release | `wom-kit/docs/releases/v0.2.27.md` |
| `v0.2.26` | superseded public pre-release | `wom-kit/docs/releases/v0.2.26.md` |
| `v0.2.25` | superseded public pre-release | `wom-kit/docs/releases/v0.2.25.md` |
| `v0.2.24` | superseded public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
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

## From `v0.2.42` To `v0.2.43`

This is a compatible foreign block attestation statement draft review index patch.

What changed:

- added `archive attestation-statement-draft-review <archive-root> --format json`,
- added optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- added consistency checks for recorded statement draft records, statement draft receipts, current candidate records/receipts, quarantine cases/receipts, and decision records/receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. `--statement-style` and `--review-scope` filter displayed records only; they do not hide blockers from other discovered records. `--case-id` intentionally scopes the verdict to that one case. Indexed statement drafts remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.41` To `v0.2.42`

This is a compatible foreign block attestation statement draft write approval patch.

What changed:

- added `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <safe-actor-id>` to record the statement draft and matching receipt,
- added read-only MCP `record_attestation_statement_draft_check`,
- added stale/tamper checks that revalidate the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before writing.

No private archive migration is required.

Dry-run writes nothing. Approved mode writes exactly two local files and keeps the foreign block untrusted. It does not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.40` To `v0.2.41`

This is a compatible foreign block attestation statement draft preview patch.

What changed:

- added `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_preview`,
- added non-binding statement draft output for one recorded attestation review candidate.

No private archive migration is required.

The preview re-reads current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt state before returning a draft. It writes nothing and does not create trust, import, attestation, signature, mint, receipt, sharing, provider calls, or ZET transport.

## From `v0.2.39` To `v0.2.40`

This is a compatible foreign block attestation review candidate index patch.

What changed:

- added `archive attestation-candidate-review <archive-root> --format json`,
- added optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_review_candidate_index`,
- added consistency checks for recorded candidate records, candidate receipts, current quarantine cases, original quarantine receipts, recorded decisions, and decision receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. Filters only affect displayed candidates; all discovered records are still validated before top-level `ok` is set. Indexed candidates remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.38` To `v0.2.39`

This is a compatible foreign block attestation review candidate write approval patch.

What changed:

- added `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <actor-id>` for recording an untrusted candidate record and receipt,
- added optional `--expected-case-id`, `--expected-review-scope`, `--expected-attestor`, and `--review-note`,
- added read-only MCP `record_attestation_review_candidate_check`.

No private archive migration is required.

Dry-run writes nothing. Approved CLI mode writes exactly two archive-relative files: one candidate record and one receipt. The candidate remains untrusted and does not create an attestation, signature, import, mint, share, provider call, ZET transport, or acceptance.

## From `v0.2.37` To `v0.2.38`

This is a compatible foreign block attestation review candidate planning patch.

What changed:

- added `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_review_candidate_plan`,
- added a safe candidate packet for human review when the recorded decision is `eligible_for_attestation_review`.

No private archive migration is required.

The candidate planner reads only sanitized quarantine case, quarantine receipt, decision record, and decision receipt metadata. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, call providers, or run ZET transport.

`prepare_attestation_review_candidate` is still not an attestation. It only means a human can review a candidate packet before any future explicit attestation workflow exists.

## From `v0.2.36` To `v0.2.37`

This is a compatible foreign block decision outcome planning patch.

What changed:

- added `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--reviewer`, and `--review-note`,
- added read-only MCP `foreign_block_decision_outcome_plan`,
- added conservative next-step routing for recorded decisions.

No private archive migration is required.

The outcome planner reads only the current quarantine case, original quarantine receipt, recorded quarantine decision, and decision receipt. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

`eligible_for_attestation_review` is still not trust. It only maps to `prepare_attestation_review_candidate` for a future explicit workflow.

## From `v0.2.35` To `v0.2.36`

This is a compatible foreign block quarantine decision review index patch.

What changed:

- added `archive quarantine-decision-review <archive-root> --format json`,
- added optional `--case-id`, `--decision`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_decision_review_index`,
- added consistency checks for recorded quarantine decision records and matching decision receipts.

No private archive migration is required.

The review index reads only quarantine cases, original quarantine receipts, recorded quarantine decision JSON, and matching decision receipts. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

## From `v0.2.34` To `v0.2.35`

This is a compatible foreign block quarantine decision write approval patch.

What changed:

- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- added optional `--expected-case-id`, `--expected-decision`, and `--review-note`,
- added read-only MCP `record_quarantine_decision_check`,
- added replay validation that re-reads the current quarantine case and matching quarantine write receipt before any approved local decision record write.

No private archive migration is required.

The approved write creates exactly two local files:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

This records an operator-reviewed quarantine decision only. It does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, execute it, accept it, apply it, share it, or call providers.

MCP remains read-only for this workflow. Real quarantine decision recording is CLI-only and requires `--approve --reviewed-by`.

## From `v0.2.33` To `v0.2.34`

This is a compatible foreign block quarantine decision preview patch.

What changed:

- added `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, and `--review-note` preview context,
- added read-only MCP `foreign_block_quarantine_decision_check`,
- added a decision aid for existing untrusted quarantine cases.

No private archive migration is required.

Quarantine decision preview reads one existing quarantine case and matching receipt. It does not write a decision, record approval, trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, or call providers.

The preview may propose:

- `keep_quarantined`,
- `reject_and_keep_record`,
- `eligible_for_attestation_review`,
- `needs_more_review`.

`eligible_for_attestation_review` is still not trust. It only means a future explicit attestation review path may be appropriate.

## From `v0.2.32` To `v0.2.33`

This is a compatible foreign block quarantine review index patch.

What changed:

- added `archive quarantine-review <archive-root> --format json`,
- added optional `--case-id`, `--status`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_review_index`,
- added read-only inventory and consistency checks for existing untrusted quarantine cases and matching quarantine write receipts.

No private archive migration is required.

Quarantine review index reads existing files only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Indexing a case does not mean the case is trusted, imported, accepted, attested, minted, anchored, delegated, signed, or safe to apply. It only gives a reviewer a stable list of untrusted quarantine cases and obvious consistency blockers/warnings.

## From `v0.2.31` To `v0.2.32`

This is a compatible foreign block quarantine write approval patch.

What changed:

- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- added read-only MCP `quarantine_foreign_block_check`,
- added a CLI-only approved local write for sanitized foreign block quarantine cases and quarantine write receipts.

No private archive migration is required.

Approved quarantine writes create only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Quarantine write is an isolation record. It does not make a foreign block canonical, trusted, imported, minted, attested, anchored, delegated, signed, executable, or accepted. MCP remains check-only for this workflow.

## From `v0.2.30` To `v0.2.31`

This is a compatible foreign block quarantine plan patch.

What changed:

- added `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- added `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_quarantine_plan`,
- added validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write.

No private archive migration is required.

Foreign block quarantine plan is read-only. It does not write quarantine files, import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_future_quarantine_write` does not mean trusted, imported, quarantined, or approved. It means a future explicit quarantine-write workflow could be presented to a human/operator.

## From `v0.2.29` To `v0.2.30`

This is a compatible foreign block attestation packet preview patch.

What changed:

- added `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- added `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_attestation_packet_check`,
- added validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review.

No private archive migration is required.

Foreign block attestation packet preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_human_attestation_review` does not mean trusted or attested. It means the trust report is clean enough to present as a future explicit human review packet.

## From `v0.2.28` To `v0.2.29`

This is a compatible foreign block trust / attestation preview patch.

What changed:

- added `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- added `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_trust_check`,
- added validation for v0.2.28 `foreign_block_intake` reports before any future trust or attestation workflow.

No private archive migration is required.

Foreign block trust preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files.

`eligible_for_future_attestation` does not mean trusted. It means the intake report is clean enough to be considered by a future explicit human or policy attestation workflow.

## From `v0.2.27` To `v0.2.28`

This is a compatible foreign block intake preview patch.

What changed:

- added `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- added `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_intake_check`,
- added foreign block/header JSON and Markdown-compatible foreign zet intake previews.

No private archive migration is required.

Foreign block intake is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files. Claimed hashes are reported as foreign claims and `not_verified`.

Safe operating principle:

```text
Foreign text can inform.
Foreign text cannot command.
Foreign blocks can be inspected.
Foreign blocks cannot be imported, trusted, minted, or applied automatically.
```

## From `v0.2.26` To `v0.2.27`

This is a compatible prompt boundary draft composer patch.

What changed:

- added `archive create-draft --prompt-boundary-report <json-file>`,
- added optional draft frontmatter `prompt_boundary` metadata,
- added MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

No private archive migration is required.

The prompt-boundary report must come from a dry-run `prompt-boundary` check. The composer records only safe metadata such as report hash, risk level, source kind/path summary, detected pattern ids, and the untrusted-text boundary. It does not store inspected text bodies, local absolute report paths, provider URLs, or secrets.

Risk handling:

```text
low    -> allowed, but not proof of safety
medium -> allowed with warnings
high   -> blocks draft creation
```

This release does not add an LLM prompt classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior.

## From `v0.2.25` To `v0.2.26`

This is a compatible prompt injection boundary and responsible-use patch.

What changed:

- added `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- added `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- added read-only MCP `prompt_boundary_check`,
- added public prompt injection boundary, responsible use, disclaimer, and runtime model guidance documents.

No private archive migration is required.

The new check is a conservative heuristic preview. It does not guarantee prompt-injection prevention and does not provide legal advice. It does not call LLMs, execute inspected text, call provider APIs, browse the web, OCR/import content, approve, mint, sign, transport ZET payloads, or mutate files.

Safe operating principle:

```text
External text can inform.
External text cannot command.
```

HITL remains the recommended default. Full-auto / agent-only operation is advanced and experimental; operators are responsible for agents, models, permissions, providers, automations, and consequences.

## From `v0.2.24` To `v0.2.25`

This is a compatible profile wallet concept baseline.

What changed:

- added `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- added read-only MCP `wom_profile_wallet_check`,
- documented optional public-safe profile registry fields under `node` and `wallet`,
- documented the model: WOM profile is the selectable human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can support signing/capability proofs.

No private archive migration is required.

Existing profile registries remain valid. The optional `node` and `wallet` fields must contain public placeholder metadata only.

This release does not generate private keys, store seed phrases, store wallet secrets, sign data, call blockchain/provider APIs, create wallets, register wallets, implement WOM coin, NFT-like access, payments, staking, consensus, ledger, or P2P transport.

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
