# Archive infra decision log: delivered letters are deleted (2026-09-30)

Status: accepted by the owner on 2026-09-30; implemented for v0.4.54.

## What was asked, and what v0.4.36 did instead

Beta letters 164 ⑧ and 168 request 8 asked three times for delivered letters
to stop sitting on the operator's PC. v0.4.36 read "정리" (clean up) as
"move": `operator-feedback-archive` copied each delivered letter and its body
receipts to a folder outside the archive and left a stub. The letters still
used the same disk on the same PC, so the request was not met.

On 2026-09-30 the owner corrected this: cleaning up delivered or resolved
letters means deleting them. The same reading applies to temporary objects
already uploaded to object storage; `object-storage-cleanup` (v0.4.49) already
deletes those permanently and is unchanged.

## Decision

The owner was offered two shapes and chose the recommended one:

- A: delete the letter, its receipts and its record, leaving nothing;
- **B (chosen):** delete the letter and its body receipts completely and keep
  only a one-line record that says "letter N was deleted".

B keeps three things working that A would break: the next letter number never
reuses a deleted number, the ledger still counts delivered letters, and
`operator-feedback-body-check` answers `deleted_record` instead of reporting a
missing letter.

## Implementation

- `operator-feedback-delete <root> --dry-run` lists the delivered,
  acknowledged and resolved letters, their receipt counts and the bytes that
  will be freed; titles and paths are never shown. `--approve` with the plan
  digest runs once under the exact approval broker (operation
  `operator_feedback_delete`, grantable: one dialog or the session grant).
- For each letter the body receipts and revision snapshots are deleted, then
  the letter, then the record is replaced by `feedback_id`, `status: deleted`,
  `deleted_at`, `deleted_from_status`, `updated_at`. No title, no body
  reference, no hash of the text remains. One deletion receipt names the plan,
  the ids and the approval.
- Letters not yet delivered (`draft`) are never touched.
- Letters that v0.4.36-v0.4.53 moved out are deleted too when the operator
  names that folder with `--moved-folder`. Each copy is recognised by its bytes
  matching the stub; a copy edited by hand, and any file WOM did not write, is
  left alone. Empty folders the move created are removed.
- A run interrupted after deleting files but before rewriting a record is
  finished by the next plan: a record whose status is `deleted` but whose files
  remain is included again.
- `operator-feedback-archive` is removed (a superseded feature is retired, not
  kept closed). Its approval kind stays in the enum only so claims and receipts
  written by v0.4.36-v0.4.53 still parse; the body check still recognises
  archived stubs until they are deleted.

## Limits

Deletion is permanent: WOM keeps no copy and cannot restore a deleted letter.
Git history or a backup made before the deletion still holds the old files;
removing those is outside this command. Validation used synthetic archives and
an injected dialog; the operator's own run is not confirmed.
