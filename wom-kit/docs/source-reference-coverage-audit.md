# Source-Reference Coverage And Recorded Storage Evidence

Status: implemented in v0.3.299

## What this command answers

This read-only command answers two different questions without mixing them:

1. Among the source occurrences that current public WOM can directly observe
   in canonical zets, which ones have a durable `source_refs` entry?
2. For an occurrence that has an exact object binding, what local storage
   evidence is recorded in the object manifest and its linked provider
   execution receipt?

Run it with the same Python interpreter that owns the WOM-kit installation:

```powershell
python -B -m wom_kit.archive_cli source-reference-coverage-audit <archive-root> --dry-run --format json
```

`-B` is required. The command refuses to inspect the archive when the
interpreter was not started in explicit no-bytecode mode.

## The two observed population families

The command traverses regular UTF-8 canonical files under `zettels/` and
counts:

- each valid current `source_refs` row; and
- each literal `[source locator omitted]` marker in a current canonical
  Notion import, when its strict frontmatter omission count agrees.

It does not invent occurrences from filenames, generated index rows, source
maps, object manifests, or finder results. Those surfaces do not provide an
exhaustive archive-wide source denominator.

Therefore every result keeps these facts separate:

```text
population_traversal_complete
archive_wide_population_authority_available: false
archive_wide_coverage_claim_supported: false
```

`population_traversal_complete: true` means the two observed families were
traversed safely. It does not mean every source attachment that ever existed
is known to WOM.

## How to read the two axes

Source-reference coverage:

| State | Meaning |
| --- | --- |
| `complete` | Every applicable observed occurrence has a valid durable source reference. |
| `partial` | Some, but not all, observed occurrences have one. |
| `none` | Observed occurrences exist, but none has one. |
| `not_applicable` | The complete observed population is empty. |
| `indeterminate` | A required population file, identity, count, or stable snapshot could not be trusted. |

Recorded storage evidence:

| State | Meaning |
| --- | --- |
| `recorded_time_full` | Every applicable observed occurrence with its assessed binding has one exact linked provider receipt accepted by the existing backup-evidence validator. |
| `recorded_time_partial` | Only some do. |
| `manifest_identity_only` | The manifest records identity, but no accepted linked provider receipt proves a recorded upload event. |
| `contradictory` | Duplicate or conflicting local evidence prevents one answer. |
| `no_evidence` | No applicable recorded storage evidence was found. |
| `not_applicable` | The complete observed population is empty. |
| `indeterminate` | Required local storage evidence could not be read or traversed safely. |

Coverage never implies storage integrity, and storage evidence never repairs a
missing source reference. A provider receipt is evidence about its recorded
event; this command does not read current object bytes or check current local
or remote availability.

## Exit codes

| Exit | Meaning |
| --- | --- |
| `0` | The defined observed population and local evidence traversal completed. Read the states; completion is not a positive coverage or live-storage claim. |
| `1` | The audit ran but a required traversal or authority was incomplete. |
| `2` | The request or startup boundary was blocked. |

Use `--max-items 1..500` to bound private-safe detail ordinals. Aggregates
still cover the full observed population. Use `--progress` for four fixed
phase labels; progress never includes a path, source value, object id, or
provider locator.

## Safety boundary

The command:

- writes no file and consumes zero generated-index rows;
- reads no object bytes;
- calls no network, provider API, credential store, MCP tool, or external
  store;
- exposes no source identifier, object identifier, provider locator, local
  path, secret, zettel title, or body; and
- validates closed result structure plus arithmetic and cross-field
  invariants before serialization.

For the wider locally recorded backup lanes, continue with:

```powershell
archive backup-evidence <archive-root> --dry-run
```

That command is also not a live remote check. Use `archive version
<project-or-archive-root> --format json` separately when the question is which
WOM-kit build is running.
