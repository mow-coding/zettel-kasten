# Backup Evidence Status

Status: implemented in v0.3.251

## Purpose

`backup-evidence` answers one narrow question from evidence already stored in
the local WOM archive:

```text
What backup evidence can WOM honestly report right now without contacting an
external service?
```

It is a read-only status command. It does not upload, download, push, restore,
or call GitHub, an object-storage provider, or an external database.

## Command

```powershell
archive backup-evidence <archive-root> --dry-run
```

Aliases:

```powershell
archive backup-status <archive-root> --dry-run
archive storage-backup-evidence <archive-root> --dry-run
```

The command returns JSON so an AI operator can explain the result in ordinary
human language without guessing from prose.

## Three Backup Lanes

| Lane | What local evidence can prove | What remains unproven |
| --- | --- | --- |
| GitHub | Nothing generic yet | A local commit or cached tracking ref does not prove that the remote currently contains it. |
| Object storage | A valid `wom_uploaded` manifest location linked to a matching provider-confirmed execution receipt proves that one object's bytes were verified at the receipt's recorded time. | It does not prove that the remote bytes still exist now. `declared_uploaded` is not byte proof. |
| External database | Nothing generic yet | Configuration, generated indexes, and database labels do not prove that a provider-specific snapshot or replica completed. |

Because the GitHub and external-database lanes do not yet have generic
provider-confirmed completion receipts, the command never reports the whole
WOM backup as complete.

## Object-Storage Statuses

- `no_remote_byte_evidence`: no receipt-linked byte evidence was found.
- `declared_only_no_wom_byte_proof`: a location was declared, but WOM did not
  verify the bytes through an execution receipt.
- `receipt_verified_partial_coverage_at_recorded_time`: some manifest objects
  have valid receipt-linked evidence.
- `receipt_verified_full_coverage_at_recorded_time`: every uniquely identified
  manifest object has valid receipt-linked evidence at its recorded time.
- `invalid_or_conflicting_evidence`: malformed, duplicate, missing, forged, or
  contradictory local evidence prevents a coverage claim.
- `incomplete_truncated`: the bounded scan stopped at `--max-records`, so no
  complete coverage claim is allowed.
- `object_manifest_missing`: the local object manifest is absent, so WOM cannot
  establish an object-coverage population.
- `not_applicable_no_manifest_objects`: the manifest contains no eligible
  object records.

Even the full recorded-time status leaves
`current_remote_availability_checked: false`.

## Safety And Privacy

The command reads only object-manifest metadata and linked object-storage
execution-receipt metadata. It does not read objet bytes or zet bodies. Output
contains counts and fixed diagnostic codes, not object ids, receipt paths,
provider/store labels, local absolute paths, source text, URLs, or secrets.

Receipt references must stay under the owned execution-receipt directory,
cannot cross symbolic links, and are size-bounded. Missing, malformed, or
contract-mismatched evidence fails closed. A bounded manifest scan can be
raised with `--max-records`, up to the fixed safety ceiling.

## Authority Boundary

Verified backup evidence never changes WOM's authority order. Reviewed local
WOM state remains canonical. External copies are recovery evidence, not silent
authority and not a replacement for local artifacts.
