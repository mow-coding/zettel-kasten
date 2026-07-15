# Decision Log: Local Backup Evidence Status

Date: 2026-07-15
Status: implemented for v0.3.251

## Decision

Add one local-only, read-only `backup-evidence` command that reports each
backup lane from evidence WOM can actually verify without silently calling a
remote service.

## Context

The local-sovereignty contract already says that GitHub backs up metadata,
object storage backs up objet bytes, and an external database may hold a map
backup or replica. That normative model did not answer whether a particular
archive had evidence for those backups. Inferring completion from a local Git
commit, `declared_uploaded`, configuration, or a generated index would create
false confidence.

## Consequences

- GitHub and external-database lanes remain explicitly unverified until a
  provider-specific completion contract exists.
- Object-storage coverage counts only valid `wom_uploaded` locations linked to
  matching provider-confirmed execution receipts.
- Coverage is labeled as evidence at the receipt's recorded time, never as a
  live remote-availability check.
- Missing, malformed, duplicated, truncated, or contradictory evidence blocks
  a complete object-coverage claim.
- The command echoes no object ids, receipt paths, provider/store labels,
  absolute paths, content, or secrets.
- Local reviewed WOM state remains canonical regardless of backup evidence.
