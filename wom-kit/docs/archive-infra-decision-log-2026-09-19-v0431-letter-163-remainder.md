# Archive infrastructure decision log — 2026-09-19, v0.4.31 (beta letter 163 remainder)

Executing model: Claude Opus 5 (implementation, tests, docs, bump, release),
under the user's standing approval to work through the backlog without
re-asking. The read-only map, design and two adversarial verifications ran as
one bounded Ultracode workflow (9 agents, `wf_24f23d02-f97`); both verdicts
refuted the first design and their fixes shape the decisions below. No client
archive, runtime, workspace or ledger was read or changed.

## Decisions

1. **Ship only what the verifiers left standing.** Create-draft hints (a)(c),
   the gating edge-target warnings, warning explanations, the preflight cause
   family plus the existing-transaction shape, and the index pre-announce
   (8a). Deferred to v0.4.32: same-generation index participation for
   discard/restore/link-revert (8b) and the bounded incremental index (8c) —
   the verifiers showed the design would have minted a generation the seal
   contract rejects, deadlocked on the mutation lock from inside the rebuild
   lock, and produced rows that differ from a full rebuild for CRLF files;
   the scratch classifier (the client's folder is probably outside the
   archive, and the v0.3.317 entry-key pins need a deliberate schema move);
   the record_type value registry (create-draft never validates facet
   values; the client is asked for the exact argv); session refs for the
   three always-dialog writers (needs a native-write kind or a
   manifest-prepared binding).
2. **Create-draft (⑦).** The blocker sentence stays (pinned) and gains the
   fixed code `ai_draft_assisted_by_required`; the option names travel in
   `next_safe_actions`, never the supplied values. `omit_when_null` is an
   additive, optional handoff-argument field (old receipts stay valid);
   `--profile-id` joins the handoff; the CLI refuses the literal `None` before
   any archive read.
3. **Edge-target warnings (11).** `discarded` = absent with a discard receipt,
   `missing` = absent without one — one absent target is exactly one code.
   The codes enter the binding basis by design: a dangling edge is a fact a
   human must see; batch plans with dangling edges must set
   `policy.allow_warnings`.
4. **Warning explanations (⑪).** Counts, categories and body line numbers
   only; matched words never appear (`matched_status_markers_echoed: false`).
   Stored inside `quality_check`, so the mint receipt carries them and
   `plan_sha256` of pre-upgrade dry-runs changes once (rerun the dry-run). The
   detector rules are unchanged; the tool-trace rule still counts distinct
   flag markers.
5. **Project-version-update cause (②).** Exception-family literals only for
   non-broker failures; broker wrappers keep the v0.4.22 allowlist (the
   negative pins stay green). `existing_transaction` is journal shape only
   and fail-quiet: `abandon_applicable` means "the journal is exactly
   `lock_backlinked`", never "a started claim exists".
6. **Index pre-announce (⑧).** `archive_index_precheck` projects the same
   evidence the writers require as fixed codes and counts; the rebuild
   commands are listed in each result's `next_safe_actions` instead of being
   prepended to `INDEX_REBUILD_NEXT_SAFE_ACTIONS` (its second line is the
   index-health line other callers depend on). The chain records
   `capture_authority_refused` so a current index with a refused manifest
   authority is not reported as stale.

## Questions for the client

- ⑦b: the exact `create-draft` argv and output that rejected a `record_type`
  value.
- 18: whether the 2.4 GB scratch folder lives under the archive root
  (`staging/incoming/...`) or outside it.
- ⑧: the `index_marked_dirty` values around the three blocks and the JSON of
  the `index` run that exceeded five minutes.
