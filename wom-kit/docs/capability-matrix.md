# WOM-kit Capability Matrix

Status: v0.3.10 project-intake cookbook checkpoint
Date: 2026-06-14
Version: v0.3.10, release candidate

This matrix is a plain-language map of what WOM-kit can do today and what is only planned.

Read it as a safety label. A row marked `read-only preview` means WOM-kit can inspect or plan something and return JSON, but it does not write files. A row marked `approval-gated write` means the CLI has a human-reviewed write path with explicit approval fields. A row marked `documented-only` means the idea is described, but no product command exists yet.

## Status Legend

| Status | Meaning |
| --- | --- |
| `implemented local command` | A local CLI behavior exists and can be run in the repository. |
| `read-only preview` | CLI and/or MCP can inspect or plan, but writes nothing. |
| `approval-gated write` | CLI can write only after explicit human approval inputs. MCP remains read-only or dry-run for that surface. |
| `local hygiene tool` | A local checker exists for public release hygiene. It does not add archive product behavior. |
| `documented-only` | Public docs or examples exist, but no product command/tool exists. |
| `not implemented` | No product behavior exists in the current release. |

## Current Capability Table

| Capability | Status in current working tree | Write behavior | Notes |
| --- | --- | --- | --- |
| Archive doctor | `implemented local command` | read-only | `archive doctor` checks archive structure, schema, manifest, receipt, and lifecycle consistency. |
| Archive `.gitignore` repair | `approval-gated write` | dry-run previews first; CLI approve appends missing safe patterns only | `archive repair-gitignore` fixes missing local-only, generated-index, harness, and content-addressed byte-store ignore patterns. It preserves existing `.gitignore` entries and does not clean files. |
| Archive frontmatter migration | `approval-gated write` | dry-run previews first; CLI approve rewrites zettel frontmatter only | `archive migrate --target frontmatter-v0.3` aligns older v0.2-draft-authored zettel frontmatter with the current v0.3 schema. Ambiguous or unsafe source values block for manual review. |
| Local objet capture | `approval-gated write` | dry-run previews first; CLI approve writes objet bytes, one manifest record, and a capture receipt | `archive objet-capture` captures explicitly approved staged files into `objects/sha256/`. Optional `--project-intake-receipt` or selection `project_intake_receipt_path` validates a decisions receipt before staged bytes are read. Sandbox-marked archives only; lossless and idempotent; never deletes or modifies staged originals. |
| Derived text capture | `approval-gated write` | dry-run previews first; CLI approve stores text, appends one derived text manifest record, and writes a receipt | `archive derive-text capture` registers already extracted UTF-8 text for an existing `object_id` in `objects/manifests/files.jsonl`. It supports single-file input and JSONL batch input with `--from-manifest`; batch output includes itemized status, action, blockers, and warnings. It writes `objects/manifests/derived-text.jsonl`, stores text bodies under `objects/derived-text/sha256/`, and indexes them for search. It does not run OCR, ASR, parsers, LLM vision, provider APIs, drafting, or minting. |
| Staged cleanup verifier | `read-only preview` | none | `archive staged-cleanup-check` reports per staged file whether it is preserved, deferred, or not preserved before any manual cleanup. Fails closed on unenumerable trees, exits 0 only when `safe_to_cleanup` is true, and never deletes. |
| Related zets (typed-edge backlinks) | `implemented local command` | read-only | `archive related-zets` traverses typed edges in both directions over the generated index, so backlinks are answerable. Redacted zettels are never returned. |
| Facet view execution | `implemented local command` | read-only | `archive view-zets` executes `views/*.yml` facet filters or ad-hoc facet queries against the generated index. List-valued facets index as repeated scalar rows; unsupported filter keys or list-valued filter inputs block instead of silently broadening results. |
| Mint lifecycle | `approval-gated write` | CLI approve writes canonical zet, receipt, and draft snapshot | Dry-run previews first. Minting is private archive memory, not public posting. |
| Delegate lifecycle | `approval-gated write` | CLI approve writes delegate receipt only | MCP delegate checks remain dry-run. Real external transport is not implemented. |
| Attest lifecycle preview | `read-only preview` | none | `attest-zet --dry-run` previews delegated receipt review without writing attestation records. |
| Anchor lifecycle preview | `read-only preview` | none | `anchor-zet --dry-run` previews local meaning anchoring without writing anchor metadata. |
| Block header preview | `read-only preview` | none | Derives a header preview for an existing draft or canonical zet. It does not modify the zet. |
| Runtime context | `read-only preview` | none | AI runtimes can confirm archive id, type, paths, policy, and safe next actions. |
| Profile registry list/resolve | `read-only preview` | none | Resolves the intended WOM profile before runtime-context or draft work. |
| Profile wallet preview | `read-only preview` | none | Wallet-ready identity model only. No keys, signing, or blockchain calls. |
| GitHub repository setup plan | `approval-gated write` | CLI approve writes local provider metadata/receipt only | Does not create a repository, configure remotes, push, call GitHub APIs, or run OAuth. |
| Objet storage setup plan | `approval-gated write` | CLI approve writes local provider metadata/receipt only | Does not create buckets, upload, sync, copy files, hash source files, or call provider APIs. |
| Provider setup status | `read-only preview` | none | CLI `archive provider-status --dry-run` and MCP `provider_setup_status` check setup-managed GitHub/object-storage bindings against local provider setup receipts. They do not call providers, verify live accounts, upload, sync, push, or write files. |
| Human artifact store plan | `read-only preview` | none | CLI `archive human-artifact-store --dry-run` and MCP `human_artifact_store_plan` plan a user-facing surface such as WordPress, Joplin, Notion, Obsidian, Evernote, or generic Markdown/workspace. They keep raw data, human-readable artifacts, and system/AI artifacts separate, and perform no provider calls, OAuth, note writes, post publishing, uploads, minting, cleanup, or ZET transport. |
| ZET surface prototype plan | `read-only preview` | none | CLI `archive zet-surface-prototype --dry-run` and MCP `zet_surface_prototype_plan` preview user-selected ZET surface prototypes for WordPress, Joplin, Notion, and Obsidian. They return surface-specific settings, risks, receipt requirements, and future adapter steps, but perform no provider calls, token prompts, note writes, vault writes, post publishing, projection receipt writes, minting, cleanup, or ZET transport. |
| Prehashed external objet ledger | `approval-gated write` | dry-run validates first; CLI approve appends external manifest records and writes a receipt | CLI `archive prehashed-objet-ledger --dry-run|--approve` handles already-hashed external content-addressed ledgers such as Notion source-export retrieval ledgers. Dry-run counts sha256/byte-size rows and planned manifest writes without echoing row values. Approved mode requires `--reviewed-by` and `--store-ref`, appends external records to `objects/manifests/files.jsonl`, and writes `receipts/prehashed-objet-ledger/*.json`. It does not read blob bytes, copy objects, upload, draft, mint, clean, call providers, or claim that `objet-capture` can skip byte verification today. MCP exposes read-only `prehashed_objet_ledger_preview` only. |
| Source intake planner | `read-only preview` | none | CLI `archive source-intake --dry-run` and MCP `source_intake_plan` provide metadata-only classification before draft creation. Optional `--project-intake-receipt` / `project_intake_receipt` validates a decisions receipt as session context only. It does not import, copy, upload, OCR, transcribe, hash file bodies, or treat the receipt as automatic execution approval. |
| Source intake plan recording | `approval-gated write` | dry-run validates first; CLI approve writes one source-intake plan record | `archive source-intake-record` validates a reviewed `source-intake --dry-run` JSON file and writes the redacted plan under `receipts/sources/` for later capture evidence. It blocks unredacted local paths, provider URLs, tokens, and secrets; it does not read file bodies, hash content, capture objets, draft, mint, upload, or clean. |
| Objet capture selection manifest | `approval-gated write` | dry-run hashes one staged file first; CLI approve writes one selection manifest | `archive objet-capture-selection --dry-run|--approve` validates a recorded source-intake plan and prepares the B4 `objet-capture --selection` JSON for one staged file. It writes only `receipts/objet-capture-selections/*.selection.json` on approve. It does not run capture, copy object bytes, append `objects/manifests/files.jsonl`, draft, mint, upload, or clean staged originals. |
| Project intake staging guide | `read-only preview` | none | CLI `archive project-intake-staging-guide --dry-run` and MCP `project_intake_staging_guide` show the recommended local objet-store intake path for one project slug. They do not create folders, move files, copy files, upload, capture, draft, mint, or clean. |
| Project intake session guide | `read-only preview` | none | CLI `archive project-intake-session-guide --dry-run` and MCP `project_intake_session_guide` show the next safe human-guided step from a project slug, staged folder, or existing decisions receipt. They write nothing, echo no decision values, read no file bodies, capture nothing, draft nothing, mint nothing, upload nothing, clean nothing, and authorize no automatic execution. |
| Project intake planner | `read-only preview` | none | CLI `archive project-intake-plan --dry-run` and MCP `project_intake_plan` plan one staged folder session with top-level counts, human review checklist, suggested classification labels, and a draft decision-record template. It does not include entry names, read bodies, recurse, classify automatically, write, upload, mint, or clean. |
| Project intake next question | `read-only preview` | none | CLI `archive project-intake-next-question --dry-run` and MCP `project_intake_next_question` return exactly the next human-review question for a new staged folder or continuing receipt. They do not echo decision values, write decisions, capture, draft, mint, upload, or clean. |
| Project intake decision template | `read-only preview` | none | CLI `archive project-intake-decision-template --dry-run` and MCP `project_intake_decision_template` build a JSON template for the next human-reviewed answer. They leave `answer` empty, do not echo previous answer values, and do not approve or write receipts. |
| Project intake answer recording | `approval-gated write` | dry-run validates first; CLI approve writes one local decisions receipt | `archive project-intake-record-answer` appends exactly one human-reviewed answer file to a new session or existing decisions receipt. It does not echo current or previous answer values, run source intake, capture objets, derive text, create drafts, mint zets, call providers, or clean staged folders. |
| Project intake decision recording | `approval-gated write` | dry-run validates first; CLI approve writes one local receipt | `archive project-intake-decisions` records human-reviewed checklist decisions under `receipts/project-intake/`. It does not run source intake, capture objets, derive text, create drafts, mint zets, call providers, or clean staged folders. |
| Project intake decision status | `read-only preview` | none | CLI `archive project-intake-status --dry-run` and MCP `project_intake_status` check one approved decisions receipt for integrity, coverage, next safe actions, and missing-question `next_review_prompts`. It does not echo answer values or authorize automatic execution. |
| Project intake item plan | `read-only preview` | none | CLI `archive project-intake-item-plan --dry-run` and MCP `project_intake_item_plan` preview the next `source-intake --dry-run` route for one human-selected file. They redact local paths, do not read file bodies or calculate content hashes, and do not generate capture selection manifests. |
| Source intake to draft composer | `approval-gated write` | CLI draft approval can write inbox draft only | Consumes validated source-intake plans without reading original source files. Valid `project_intake_context` is preserved as receipt evidence in draft `source_intake` metadata and later mint metadata without copying decision answer values. Minting remains separate. |
| Prompt boundary check | `read-only preview` | none | Heuristic local check for obvious prompt-injection and unsafe-agent strings. Not complete prevention. |
| Prompt boundary to draft composer | `approval-gated write` | CLI draft approval can write inbox draft only | Carries untrusted-text boundary metadata into draft/mint metadata where supported. |
| Foreign block intake | `read-only preview` | none | Inspects shared block/header JSON or Markdown-compatible foreign zets without trusting or importing. |
| Foreign block trust preview | `read-only preview` | none | Classifies intake as reject, manual review, or future attestation candidate. It grants no trust. |
| Foreign block attestation packet preview | `read-only preview` | none | Prepares a human-review packet. It creates no trust, receipt, attestation, or signature. |
| Foreign block quarantine plan | `read-only preview` | none | Proposes future holding paths without writing quarantine files. |
| Foreign block quarantine write | `approval-gated write` | CLI approve writes untrusted quarantine case and receipt | The foreign block stays untrusted and unimported. |
| Foreign block quarantine review index | `read-only preview` | none | Indexes existing untrusted quarantine cases and matching receipts. |
| Foreign block quarantine decision preview | `read-only preview` | none | Proposes a human decision path without recording a decision. |
| Foreign block quarantine decision write | `approval-gated write` | CLI approve writes decision record and receipt | Keeps the foreign block untrusted and unimported. |
| Foreign block quarantine decision review index | `read-only preview` | none | Reviews recorded decisions and receipts without changing trust state. |
| Foreign block decision outcome plan | `read-only preview` | none | Routes one recorded decision to the next safe non-mutating path. |
| Attestation review candidate plan | `read-only preview` | none | Plans a human-review candidate from an eligible recorded decision. |
| Attestation review candidate write | `approval-gated write` | CLI approve writes untrusted candidate and receipt | Does not create an attestation, signature, trust, import, or ZET transport. |
| Attestation review candidate index | `read-only preview` | none | Reviews recorded untrusted candidates and receipts. |
| Attestation statement draft preview | `read-only preview` | none | Creates a non-binding draft preview only. It is not an attestation. |
| Attestation statement draft write | `approval-gated write` | CLI approve writes untrusted statement draft and receipt | Does not create trust, signatures, attestation, acceptance, or transport. |
| Attestation statement draft review index | `read-only preview` | none | Reviews recorded untrusted statement drafts and upstream chain consistency. |
| Attestation statement draft decision preview | `read-only preview` | none | Proposes one safe next route without recording acceptance or creating trust. |
| Publication surface baseline | `documented-only` | none | Describes future projection surfaces such as WordPress-like posts. No provider posting exists. |
| Projection plan | `read-only preview` | none | Plans one local zet projection for one declared surface kind. No rendering, receipt, provider call, or publish action. |
| Closed sharing model | `documented-only` | none | Describes the future closed sharing/SNS layer above GitHub, objet storage, and database infrastructure. |
| Radio-frequency recommendation model | `documented-only` | none | Describes future user/node-owned recommendation selectors. No fetching, ranking, or feed update exists. |
| Shared update record baseline | `documented-only` | none | Defines a future receiver-side review artifact and sanitized example. |
| Shared update record review preview | `read-only preview` | none | Reviews one local archive-contained shared update JSON record before any receiver-side renewal write exists. |
| Shared update record review index | `read-only preview` | none | Indexes direct-child local shared update JSON records by reusing the single-record review policy. Writes nothing and records no review. |
| Shared update attestation/review write | `approval-gated write` | CLI approve writes one local review record and one receipt | Reuses the shared update record review preview policy, refuses replay/overwrite, and keeps trust/import/acceptance/signature/anchor/feed/provider/projection/real ZET transport closed. MCP exposes no write/apply sibling tool. |
| Shared update route preview | `read-only preview` | none | Maps one reviewed shared update record to a candidate receiver-side route pointer: `delegate`, `attest`, `anchor`, or `none`. It points to existing canonical commands, writes nothing, and does not duplicate lifecycle preview logic. |
| ZET transport threat model / would-transport plan | `read-only preview` | none | Plans method-specific risks and future controls for `key-sharing`, `radio-frequency`, or `mirroring` after the shared update review policy passes. No real transport. |
| v0.2.x freeze / v0.3.0 entry boundary | `documented-only` | none | Closes the v0.2.x line as a conservative local-first checkpoint and proposes one narrow receiver-side approved write as the first v0.3.0 boundary. |
| Public release link hygiene | `local hygiene tool` | none | Checks repository Markdown links for release note copy safety. No GitHub Release edit or external URL fetch. |
| Korean product-language hygiene | `local hygiene tool` | none | Checks public Markdown drift against the Korean product-language baseline. No auto-rewrite. |
| Public privacy hygiene | `local hygiene tool` | none | Checks public files for obvious local path, token, private key, seed phrase, and private endpoint leaks. |
| Release readiness gate | `local hygiene tool` | none | Runs the public hygiene checkers together. It is not CI or branch protection. |
| Main branch protection readiness | `documented-only` | none | Documents a staged path toward future repository settings. It changes no GitHub settings. |
| Real ZET transport | `not implemented` | none | No send/receive relay, P2P, inbox transport, or transport worker exists. |
| Public proof anchoring | `documented-only` | none | Future minimal proof concept only. No anchoring, chain registry, validator behavior, provider call, or public proof write exists. |
| DID-compatible identity research | `documented-only` | none | Future research only. No DID method, DID registry, wallet creation, key custody, or signing behavior exists. |
| Key-sharing registry | `not implemented` | none | No key exchange, key registry, private-key custody, or wallet signing exists. |
| Radio-frequency access | `not implemented` | none | No subscription, channel access, or frequency access control exists. |
| Mirroring delivery | `not implemented` | none | No mirror/re-project delivery pipeline exists. |
| Neighbor feed update | `not implemented` | none | No receiver-side feed mutation exists. |
| Recommendation execution | `not implemented` | none | No selector execution, fetching, ranking, or automatic recommendation update exists. |
| Provider sync / WordPress | `not implemented` | none | No WordPress publishing, provider sync, external provider write, or provider API workflow exists. |
| Redis / queues / workers | `not implemented` | none | No background job infrastructure exists in the product layer. |
| System token / validator governance | `not implemented` | none | No system token, validator governance, public chain, payment, staking, or consensus behavior exists. |
| Payments / blockchain / token / consensus | `not implemented` | none | No WOM coin, NFT-like access, staking, payment, ledger, consensus, or blockchain mechanics exist. |

## v0.3.0 Boundary Status

The v0.2 line closed after this sequence:

1. `v0.2.57`: capability matrix and README readability cleanup.
2. `v0.2.58`: shared-update review index, read-only.
3. `v0.2.59`: ZET transport threat model and dry-run would-transport plan, with no real transport.
4. `v0.2.60`: freeze/checkpoint documentation and v0.3.0 entry boundary, with no product behavior.

v0.3.0 implements that boundary as a CLI-only shared update attestation/review record plus receipt. It is replay-gated, human-approved, local-first, and body-safe, and it still avoids real transport, anchors, trust graph mutation, provider sync, full-auto behavior, payment layers, public proof anchoring, DID/wallet/key custody, and blockchain/token mechanics.

## Review Context

A big-picture external review summarized the v0.2.56 line as `GO WITH CAUTIONS`: the WOM vision is coherent and the safety-first pattern is credible, but the project has readability debt and too many similar preview ladders for new readers.

The v0.2.57 response was deliberately small:

- add this matrix,
- shorten the top-level README status summary,
- restore the missing `v0.2.55` tag in README release lists,
- document the v0.2.x closing plan,
- avoid any new product CLI, MCP, service, provider, transport, trust, import, attestation, signature, anchor, or full-auto behavior.

The v0.2.58 response keeps the same safety shape while adding one read-only index over local JSON records. It still avoids shared-update review writes, feed updates, trust/import/acceptance, attestation/signature writes, anchors, provider calls, receipts, ZET transport, and full-auto behavior.

The v0.2.59 response adds one read-only would-transport planner. It still avoids real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, feed updates, trust/import/acceptance, attestation/signature writes, anchors, provider calls, receipts, queues/workers, recommendation execution, and full-auto behavior.

The v0.2.60 response is documentation, version, and test coverage only. It closes v0.2.x as a conservative local-first checkpoint, records the proposed v0.3.0 first boundary, and still avoids product CLI/MCP/service changes, schemas, real ZET transport, trust/import/acceptance/anchor mutation, attestation/signature writes, provider sync, queues/workers, DID/wallet/key custody, public proof anchoring, blockchain/token mechanics, and full-auto behavior.

The v0.3.0 response opens only the CLI local review record and receipt for shared update attestation/review. It still avoids MCP write/apply tools, real ZET transport, key creation, feed updates, trust/import/acceptance, real attestation/signature writes, anchors, public proof, provider sync, projection writes, queues/workers, DID/wallet/key custody, blockchain/token mechanics, and full-auto behavior.

The v0.3.1 route-preview response adds only a read-only router over an already
reviewed shared update record. It points to existing delegate/attest/anchor
surfaces, writes nothing, exposes no MCP write/apply tool, and still avoids
real transport, trust/import/acceptance, real attestation/signature writes,
anchors/apply/public proof, provider sync, queues/workers, wallet/key custody,
blockchain/token mechanics, and full-auto behavior.
