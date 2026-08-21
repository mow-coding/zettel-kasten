# Decision Log: v0.4.1 Letter 140 Exact Zettel–Objet Link Recovery

Date: 2026-08-21

## Context

Letter 140 reported that v0.4.0 fixed every legacy compound approval path
closed, including the one narrow write needed to attach one already-manifested
Objet to one reviewed Zettel. The same letter also asked for a trustworthy
machine-readable inventory instead of manually maintained command counts.

Letter 139 separately requests Git commit and remote backup automation. That is
a different, archive-wide and network-mutating authority surface and is not
part of this recovery release.

## Decision

Release v0.4.1 as a narrow recovery release with these boundaries:

- reopen only `zettel-objet-link --approve`;
- keep link revert, Objet capture, and project version update approval paths
  fixed closed;
- bind the write to an exact parser-derived plan, archive identity, Zettel and
  manifest state, reviewed effect set, reviewer, and one-use exact-human claim;
- hold a persistent per-Zettel control lock and every target parent identity,
  revalidate under that lock, publish canonical bytes through a plan-bound
  exact compare-and-swap, write snapshot/receipt evidence, and verify exact
  readback plus the manifest target at the final success point;
- approval-bind both deterministic compare-and-swap residue paths and retain
  all recovery evidence on failure; an ambiguous residue may contain full
  private Zettel bytes and is never auto-deleted;
- on Windows, use retained exact-file handles and two no-replace
  `FileRenameInfo` moves instead of a backup-overwriting replace primitive;
  accept a recoverable canonical-name gap so a raced `.previous` or canonical
  occupant is preserved rather than destroyed;
- require both ID and direct-path selectors to scan `zettels/` plus `inbox/`
  under held directory identities and prove exactly one matching Zettel id;
  a filename is selection input, not authority to skip duplicate detection;
- repeat that uniqueness/identity proof under the control artifact before the
  write and at the final readback boundary, rolling the canonical bytes back
  and retaining evidence if a same-ID file appears during publication;
- make each two-root proof one stable namespace snapshot: hold every directory,
  compare complete inventories and each Markdown file's identity, version
  token, and digest across repeated validation; capture the POSIX archive-root
  inventory before any missing-child probe; and on
  Windows arm `ReadDirectoryChangesW` guards before scanning plus one final
  archive-root subtree closing guard that remains active while earlier watches
  are cancelled; any move, rewrite, overflow, unsupported watch, or ambiguous
  completion fails closed;
- make the final manifest and Zettel proofs one joint stable authority point:
  hold the exact manifest parent/file identity, metadata, and bytes across a
  complete Zettel snapshot revalidation while the Windows archive-subtree
  closing guard remains armed, and compare the same held observations on
  POSIX; two non-overlapping passing checks cannot compose a success;
- parse held `archive.yml` bytes independently at the operation core and live
  CLI approval boundary with duplicate-key rejection, bounded JSON-safe tree
  normalization, and the exact-human archive-id grammar;
- before a Windows move, admit only matching, completely verified regular-file
  metadata: `BackupRead` must expose only the unnamed default data stream, so
  alternate streams, EAs, object IDs, sparse data, or unknown metadata fail
  closed instead of being silently discarded;
- remove a verified old `.previous` name only through `FileDispositionInfoEx`
  with delete, POSIX-semantics, and ignore-readonly flags, never through an
  ordinary delayed-delete fallback; when unsupported, retain canonical-new and
  `.previous`-old for explicit reconciliation;
- publish the full parser-derived approval-status inventory through the
  machine-readable capabilities response;
- use the common `wom-kit/cli-error/v0.1` envelope for usage, policy, and
  precondition failures without reflecting private input;
- package only the current v0.4.1 release note while preserving historical
  source release notes and their recorded digests;
- leave the repository public only after complete-history privacy scanning
  found no issued credential requiring rotation or history rewrite.

## Consequences

One reviewed Zettel–Objet link can complete end to end in v0.4.1. Broader
writers do not inherit this authority. The project updater remains read-only
because its current fetch-first workflow mutates before the exact target and
effect set can be approved. Letter 139 proceeds separately, beginning with a
read-only Git backup inventory and reconciliation plan before any commit or
push executor is considered.

Release completion requires the full test shards, independent P0/P1 review,
clean PR CI, published wheel verification, and a fresh v0.4.0-to-v0.4.1 tool
upgrade test from the public release URL.
