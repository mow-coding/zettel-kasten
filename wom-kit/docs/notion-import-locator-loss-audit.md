# Notion Import Locator-Loss Audit

Status: v0.4.14 read-only census and receipt-bound resolution evidence
Date: 2026-08-29

`notion-import-locator-loss-audit` measures what was lost when a historical
Notion import replaced source locators with:

```text
[source locator omitted]
```

The command remains read-only. v0.4.14 extends the original census so it can
also answer which historical omissions have been accounted for by a fully
verified recovery chain. It answers:

- how many imported zets contain the marker;
- how many markers exist in their bodies;
- whether that number still agrees with the import-time
  `source_locator_omitted_count`;
- whether `source_page_id` survived as a possible source-mirror join key;
- which known Notion import family produced each affected zet;
- how many occurrences remain unresolved after verified-reference evidence;
- whether an old classification ledger was safely skipped or current evidence
  conflicts and must fail closed.

The audit is not the recovery writer. The separate receipt-bound
`external-locator-record` recovery mode creates an exact plan and may write only
after a native human decision. Publishing or installing WOM-kit does not run
either command on a client archive.

## Command

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --dry-run `
  --format json
```

Short alias:

```powershell
archive notion-locator-loss-audit <archive-root> `
  --dry-run `
  --format json
```

Use `--max-items N` to limit returned per-zet summaries. The command still
scans the complete archive so its aggregate counts remain complete.

For a large archive, add `--progress`. Content-free progress is printed to
stderr every 250 zets while the final text or JSON result remains on stdout:

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --dry-run `
  --progress `
  --format json
```

To inspect the complete historical markup-normalization receipt inventory
without making a person count receipts or copy their private paths, use:

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --all-markup-receipts `
  --dry-run `
  --progress `
  --format json
```

This adds a read-only `orphan_recovery` classification plan to the result. The
optional `--expected-orphan-row-count` is a machine-rechecked drift guard for a
workflow that already has a bound expectation; it is not a number the human is
expected to calculate.

The matching write-capable command family is first previewed with:

```powershell
archive external-locator-record <archive-root> `
  --all-markup-receipts `
  --dry-run `
  --progress `
  --format json
```

If the exact plan is valid, replacing `--dry-run` with `--approve` opens one
native decision. WOM derives and checks the manifest itself; the person decides
only whether to run or cancel the plainly described effect.

## Reading The Result

Important summary fields:

- `affected_zettel_count`: imported Notion zets whose body contains at least
  one omission marker;
- `body_marker_count`: total markers currently found in those bodies;
- `frontmatter_omitted_count`: total import-time count recorded on those same
  zets;
- `marker_frontmatter_count_delta`: current markers minus recorded markers;
- `count_mismatch_zettel_count`: zets that require occurrence alignment before
  any restoration proposal;
- `source_page_id_present_count`: affected zets that retained the intended
  source-page join key;
- `source_page_id_missing_count`: affected zets that require a different,
  separately reviewed provenance route;
- `verified_reference_resolution_count`: occurrences reduced only by a verified
  v0.2 classification ledger and its complete exact-operation evidence;
- `verified_reference_review_pending_count`: occurrences that the same ledger
  deliberately leaves for review;
- `unresolved_occurrence_count` and `unresolved_occurrence_state`: the remaining
  known count, or `unknown` when evidence is incomplete or conflicting;
- `skipped_legacy_resolution_ledger_count`: structurally recognized v0.1
  ledgers that were counted but not trusted;
- `conflicted_resolution_target_count`: targets removed from automatic trust
  because verified candidates disagreed.

Each returned item has one count state:

- `exact`;
- `body_marker_count_exceeds_frontmatter`;
- `frontmatter_count_exceeds_body`.

It also has one source-evidence state:

- `source_page_join_key_preserved`;
- `source_page_join_key_missing`.

`source_page_id` values themselves are never returned.

When `--all-markup-receipts` is used, `orphan_recovery.summary` partitions every
transaction-created omission occurrence into:

- `normal_maintain_count`: the canonical body already retains the safe marker
  state;
- `resolved_by_verified_reference_count`: exact historical replay proves that a
  bound reference replaced the omitted occurrence;
- `restore_ready_count`: exact evidence supports restoring only the omission
  marker field;
- `review_pending_count`: evidence is incomplete, divergent, or otherwise too
  weak for automatic change.

Those counts must cover the complete bound occurrence set. A partially covered
target contributes its proven occurrences to resolved and the remainder to
review pending; it is never rounded up to resolved.

## Why Count Agreement Matters

An omission marker is only a placeholder. It does not identify the original
URL, its source block, or its exact position among several source locators.

If the current marker count differs from the import-time count, a later tool
must not pair markers and source URLs by list position. It must first prove an
occurrence-level alignment from retained source evidence. Otherwise one wrong
match can put a valid URL into the wrong sentence.

Even an exact count is not permission to write. v0.4.14 may reduce a loss count
only when a private v0.2 ledger, its `ExactOperationManifest v1`, authenticated
operation receipt and checkpoints, current canonical identity, and exact
reference evidence all agree. A sidecar, occurrence anchor, filename, title, or
v0.1 ledger alone is not authority.

If two otherwise verified records disagree about one target, WOM removes that
target from the trusted set and reports a blocker. Later matching evidence must
not silently restore that trust.

## Boundary

The audit command is CLI-only, read-only, and requires `--dry-run`.

It reads non-redacted imported Notion zet bodies only to count the exact
omission marker. It does not return body text, nearby context, provider URLs,
raw frontmatter values, source-page ids, page titles, account data, secrets,
or absolute local paths.

The base audit reads no source mirror, object bytes, source map, or download
ledger. It may read private locator sidecars and local-recovery ledgers, and it
accepts a resolution only after verifying the complete exact-operation chain.
With `--all-markup-receipts`, it also reads the safely discovered receipt,
snapshot, and binding-manifest evidence needed to return the nested recovery
plan. Neither mode calls a provider or model or writes a zet, facet, edge,
receipt, index, diagnostic, or plan file.

Generic provider-locator reconstruction remains unimplemented. The v0.4.14
recovery writer can restore only a receipt-proven omission-marker field or
record a private classification ledger; it does not invent a locator. Since
v0.3.287, the separate read-only
[`notion-import-locator-evidence-plan`](notion-import-locator-evidence-plan.md)
can validate an explicitly reviewed occurrence mapping against exact current
canonical bytes. It still performs no restoration by itself.

## Safe Follow-Up

1. Run the audit with `--all-markup-receipts`; let WOM discover and count the
   private evidence.
2. Check the plain classification and blocker summary. Do not ask the person to
   compare hashes, count rows, or copy private receipt paths.
3. If the plan is valid, run the same evidence set through
   `external-locator-record --dry-run`, then let the person choose run or cancel
   in the native approval window.
4. After an approved execution, rerun this audit. Only a verified v0.2 ledger
   and its complete exact-operation evidence may reduce the unresolved count.
5. Leave `review_pending` and conflicting targets unchanged until stronger
   provenance exists. Do not infer a page or locator from a similar title,
   neighboring id, filename, or body position.
6. Treat a public release, installation, or dry-run as capability evidence only.
   Client recovery is complete only after that client's approved execution,
   durable receipt, and independent post-write audit succeed.
