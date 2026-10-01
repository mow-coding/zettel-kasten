# Archive infra decision log: letter 179 (2026-10-01)

Status: implemented for v0.4.56 under the owner's standing instruction to
finish every implementable item before the reply.

Letter 179 came from v0.4.54, which the customer installed successfully
(result delivery acknowledged). Four observations remained.

## 1. An R2 connection made earlier had to be typed in again

The customer's earlier R2 connection lives in a key file that an earlier
script read. WOM only offered the two masked windows, and the plaintext
migration readiness said "planned, not implemented". The person said: typing
keys again for a connection they already made is not acceptable.

Decision: `object-storage-credential-store --from-file <file>
--access-key-field <name> --secret-access-key-field <name>` reads dotenv,
INI (`section.key`, e.g. rclone.conf) or JSON (dotted path) files. The plan
binds the file by a digest of its path, size and change time (never its bytes;
the path is never echoed). The approval runs under the exact broker as the
grantable kind `object_storage_credential_import` (one dialog, or the session
grant the person already gave). An isolated child reads the two fields,
validates them, writes the exact Credential Manager targets, wipes its buffers
and returns only the two `credential-manager:` refs. The original file is left
unchanged; the person may delete it once the refs work.

## 2. The Git backup preview stopped with receipt_inventory_drifted

Reproduced on Windows with the real CLI and nothing writing: on Python 3.12 a
directory's `st_size` flips between 0 and its real size with no activity, and
the preview's receipt recheck compared it, so a several-minute preview on a
large archive almost always stopped. Decision: directory size and permission
bits are left out of the receipt identity (file type kept; file id, size,
mtime, creation time and link count still catch an added, removed or
rewritten receipt), as `project_runtime._stat_identity` has done for runtimes
since v0.4.19. The result now carries `receipt_context.drift` (counts by kind
and WOM category, never a path, `effects_state: none`, resumable). The session
heartbeat reports its own elapsed time per stage instead of repeating the last
stage value.

## 3. Offload was blocked by a valid draft

A `reviewed_session_evidence` draft receipt has no `object_id` by contract;
offload's retention check read `object_id` from every source and counted it
unreadable, blocking every offload and remote cleanup. Decision: such a
receipt is validated against its own v0.2 contract (which refuses any extra
key, so an `object_id` cannot hide there); real corruption still blocks.

## 4. 240 offloaded objects came back and could not be freed again

Offload decided "already offloaded" from the manifest alone. Objet capture's
`re_materialize` writes the same bytes back without touching the row (found
in the code; which writer did it on the customer's PC is not verified).
Decision: when the row says offloaded and the file exists, offload hashes it:
verified bytes are offloaded again under the same remote proof
(`offloaded_bytes_reappeared_count`), absent stays already offloaded, other
bytes are a conflict and stay.

## Also

- After a successful update, recommended `.gitignore` rules missing from the
  archive are named with `repair-gitignore` as the next step (the customer had
  to find it).
- `activity-cleanup --status` returns `completion_boundaries`: remote
  verification (past receipts only), original cleanup, local space, Git backup
  (not covered; next command named), closure and cost, so an install or a
  synthetic test is never read as the task being done.

## Not verified

The customer's own key file format and fields, their Windows build, which
writer recreated their 240 files, and their own runs.
