# Decision Log - v0.3.296 Private Objet Metadata Writer

- Date: 2026-08-01
- Status: accepted implementation decision; release remains gate-dependent
- Related release: v0.3.296
- Exact predecessor: `d73c10e13b9bdc714aa5346c4a2327cd7c48559f`

## Context

v0.3.295 defined how one private source-name observation can remain an alias
to a SHA-256 objet without becoming identity or leaking onto a public
projection. Letter 105 also exposed the operational gap: a schema and pure
normalizer do not register reviewed evidence in a real archive.

The writer must preserve private authority across interruption without
silently absorbing the separate work for indexing, finding, provider access,
or object-byte verification.

## Decision

Implement one CLI-only, approval-gated lifecycle:

1. Parse one bounded private intake with duplicate-key, non-finite-number,
   UTF-8, Unicode-scalar, type, and closed-field enforcement.
2. Derive one canonical v0.3.295 row and one deterministic content-free plan;
   never trust caller-supplied aliases, labels, normalized names, or search
   keys.
3. Require the exact intake and plan digests, a safe `operator:` token,
   explicit private review, and truthful all-other-writer quiescence before
   approval.
4. Support approval mutation only on Windows 10 version 1607+ or Windows 11
   over local NTFS, using retained Win32 identities and the hardened
   object-manifest/private-manifest lock pair.
5. Validate the complete existing row/receipt authority chain before any new
   append.
6. Publish one deterministic interruption journal, append one canonical
   LF-terminated row, and publish one immutable privacy-matched receipt.
7. Make exact replay idempotent; separate pre-manifest rollback from append;
   finish an interrupted append only from exact journal authority; preserve
   ambiguous evidence under `manual_hold`.
8. Keep observation-time and execution-time holds distinct. An execution-time
   hold retains the accepted plan and adds only the closed,
   non-authoritative `hold_context`.

## Safety And Claim Boundary

- The mutation profile is
  `windows_ntfs_win32_process_interruption/v0.1`.
- The quiescence affirmation includes every other WOM and non-WOM archive
  writer. Locks remain defense in depth, not permission for concurrent
  production writes.
- Process-interruption evidence does not prove sudden-power-loss
  directory-entry or volume-metadata durability.
- A restricted row produces a restricted receipt.
- Registration proves neither object-byte availability nor source coverage.
- The writer opens no objet bytes and calls no provider, network, credential
  store, external local store, database, or index.
- v0.3.296 adds no MCP writer, private finder, search projection, migration, or
  UI.

## Consequences

- A reviewed private observation can become one append-only local row and one
  immutable receipt with deterministic replay, rollback, and recovery.
- `private_original_name_metadata` becomes `unchecked` with
  `private_metadata_rediscovery_not_checked`; it does not become complete.
- v0.3.297 still owns receipt-bound index ingestion and freshness, v0.3.298
  owns the private finder, and v0.3.299 owns coverage-versus-integrity
  reporting.
- “Durable” in the record/schema name is limited by the explicit platform and
  interruption claim above.

## Public AI Contribution Provenance

| Field | Recorded value |
| --- | --- |
| Task roles | release supervision, implementation slices, independent review, and release-evidence review |
| Observed product/app | Codex desktop app with separate Codex tasks |
| UI label | `Codex` product label observed; no backend model identity inferred from it |
| Agent system identity | Codex, an agent based on GPT-5; family-level system context, not an exact backend model attestation |
| Backend model id | `not_exposed` |
| Client/session model telemetry | `not_exposed` |
| Model transition | `not_observed` |
| Exact input commit | `d73c10e13b9bdc714aa5346c4a2327cd7c48559f` |
| Output artifacts | v0.3.296 source, schemas, tests, docs, package manifest, and later exact release evidence |
| Exact output commit | recorded by the final reviewed merge/tag/release evidence; not guessed in this decision record |
| Review evidence | exact-directive independent review, focused contract/writer/Win32 tests, full suite, installed-wheel checks, exact-final-tree audit, and public release checks are separate required gates |
| Final authority | the human release operator reviews the evidence and makes the final release decision |

This provenance records only observed product/task facts. It does not attribute
work to Claude, Fable, Opus, or any other model label without direct evidence,
and it does not infer a backend model from branch names, agent roles, writing
style, or confidence.
