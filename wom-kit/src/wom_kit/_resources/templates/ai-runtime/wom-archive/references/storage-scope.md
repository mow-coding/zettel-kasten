# Object-storage scope and interruption

- For object-storage upload, restore and offload, default to this session's
  capture scope. A missing session or missing attribution is not permission to
  select the archive. Use `--captured-by-session` for an explicitly delegated
  session, `--object-list` for an exact delegated set (including multiple sessions),
  or `--all-sessions` only when the user delegates the whole archive. Never treat
  `--local-bytes-only` or `--max-objects` as a session selector. Check the scope
  and excluded counts before applying the matching plan.
- For a stopped partial upload that must not continue, inspect the original
  plan with `--abandon-started-upload --dry-run`, its exact resume identifiers
  and reviewer; then use the matching `--approve`. Keep existing effects and
  receipts. Start a fresh scoped plan afterwards; do not claim remote success
  or rollback from abandonment. Generic claim finalize is not this procedure.

- Object-storage keys belong in the Windows Credential Manager, like the
  desktop apps' keychain: run `object-storage-credential-store <archive-root>
  --store-slug <slug> --dry-run`, then its `--approve --expected-request-sha256`;
  the human types each key into WOM's masked window and the result returns the
  two `credential-manager:` refs to use. An `env:` ref ends with its process. If a
  preview reports `credential_refs_state: unresolved`, stop; for an unfinished
  `activity-cleanup`, rerun `--reconcile --dry-run` with
  `--rebind-access-key-id-ref` and `--rebind-secret-access-key-ref`, then the
  matching `--approve`. Completed items are not reprocessed; never put a key in
  chat, a file, or a command line.
- Shared archive files (the objet manifest, policy, operational context,
  ledgers) carry several activities' changes and belong to the archive, not
  to one session. A session- or list-scoped Git backup leaves them out by
  design. Back them up with one archive-wide `git-backup-plan --dry-run` only
  after the human agrees to include every activity's pending changes in that
  commit; never split a shared file by hand. Session-start Git attention
  reads the locally cached remote ref, not the remote; the plan's dry-run is
  the live check.
- A session-scoped Git preview (`git-backup-reconcile-plan` with the session
  refs) selects a file only when an authenticated record proves the whole
  file is this session's output. Read `session_backup_coverage`: what was
  selected by kind, the roles of all changed paths, and this session's own
  approvals whose Git changes are `not_provable_as_session_owned_yet`
  (objet registration and others). Since v0.4.66 this session's
  zettel-objet links are selected: the changed zettel only when it has no
  other pending edit and no other conversation's link. Report its
  `plain_summary`. A small selected count is not a backup of the whole
  conversation and not an error; the rest stays uncommitted. Do not rerun
  the preview to get a different answer, and do not commit by hand. Git
  never holds objet bytes: report their remote preservation separately.
- A long preview is read-only: progress lines carry `current` and `total`.
  If `current` has not moved for 5 minutes, interrupt it and report the last
  line; nothing needs resuming.
- `writer_unavailable` on an upload preview is the store label, never the
  writer, a lock, a credential or the session: use a label from
  `registered_store_refs`. If `--this-session` selects nothing, the captures
  were approved through a window: `object-storage-scope-list --approval-id
  <your own batch approval ids> --output <private file>`, then `--object-list`.
- If an `activity-cleanup` ends partial, change nothing by hand and do not
  start it again: read `pending_item_diagnosis` in the `--reconcile --dry-run`
  result (each unfinished item's step and route) and approve that exact plan
  once. An item routed `offload_effects_unproven_file_kept` stays by design;
  report it to the human instead of deleting it.
- If the human already connected the store through a key file (an earlier
  script read it), do not ask them to type the keys again: add `--from-file
  <that file> --access-key-field <name> --secret-access-key-field <name>` (the
  names the old script used; never open the file yourself). One approval, or
  the session grant, moves both keys into the Credential Manager.

- Archived mail (.eml objets) can be read as threads: run `archive mail-threads
  <archive-root> --build`; text records per mailbox account land under
  `db/mail-threads/<generation>/`. They are a rebuildable snapshot, never
  evidence or a zet; cite the mail objets when a thread becomes a zet.

## Classify before upload

The helper AI owns classification when the user delegates cleanup. Inspect
contents, how files were produced, references and recovery needs. Do not ask
the user to label every file and do not upload the whole working folder first.
Use the private `activity-cleanup` request to record each role and its reason:

- Preserve originals, useful deliverables and recovery evidence.
- Discard proven disposable caches, intermediates and redundant temporary
  copies without intake or upload: `role: temporary`, `disposition: discard`,
  `discard_intent: true`. Record reproducible inputs/steps, verified retained
  copies including alternate streams, or the user's delegated disposal intent.
- Retain uncertain or still-used files: `disposition: retain`. No upload or
  deletion; explain the remaining uncertainty without calling cleanup complete.

- A real secret file (keys, tokens) is `role: secret_config`. It is never
  uploaded. Use `disposition: retain`, or, only after the human confirms for
  that file that its secret values are kept elsewhere, `disposition: discard`
  with `discard_intent: true` and `secret_values_kept_elsewhere: true`. An
  example file without secret values is an ordinary `source`. Judge each
  file by its content, not its name.
- A file with several hard links (one file, several names): make every link
  its own item with the same role and disposition; `fsutil hardlink list
  <path>` lists them. WOM preserves the bytes once and removes each link.
  If the plan reports `links_outside_selected_roots`, the file is shared
  outside this activity: leave it, tell the human, and never copy, unlink or
  replace it to get past the check.

A filename, age or ignore rule alone is not disposal evidence. Never dispose
of unique work, Git history or other activities' dependencies.
Temporary files cannot silently use `preserve`; meaningful intermediate
evidence needs the appropriate role and reason. A valid full-access grant
covers the official child operations without additional approval windows.
Do not delete already-uploaded remote temporary objects through local cleanup.

Report the result with its `plain_summary`: "selected items done" and "folders
empty" are two answers (`selected_items_complete`, `folders_empty`). Count
distinct files, not paths ("5 files under 10 paths"). Keep three things
apart: files still on this PC, what is published online, and the private
backup. Say what the human must do and what you will do; a blocker code alone
is not an answer.

Folders are a third answer. `folders_empty` means "no files"; `folders_removed`
says whether the selected folders are gone. When every file is finished and a
run still ends `partial` with `state_detail:
selected_items_complete_folder_removal_unfinished`, nothing needs reconciling
or re-uploading. Close out the folders with a new request: a new
`activity_id`, `"items": []`, the same exact `roots`, and
`remove_empty_directory_trees` naming them. Preview it (`directory_trees`
gives the counts; `--private-plan-output` the exact list), then approve. Only
unchanged empty folders are removed, deepest first; a folder that holds a
file, link or junction stays with its parents and that is a finished state.
A `.git` with no file left in it is treated as empty folders. Never delete
folders by hand, recreate files, or fake a repository to pass a check.

A secret file whose owner does not know where else its values are kept stays
`retain`. Tell the human, by variable NAME only, what the file holds; a
provider showing that a name is registered does not prove the value can be
read back or equals the local one. The human saves the values somewhere they
can read them (password manager, an encrypted backup) and says so; only then
may the file be discarded. Never print, upload or compare secret values.

Say which of four states applies: waiting for approval, processing, ended, or
ended with folders or protected files left. A recorded state is not a running
process; report `plain_time_summary` rather than guessing where time went.

## Already-uploaded disposable files

The helper AI owns this classification when cleanup has been delegated. Read
the signed private inventory and the actual content, creation purpose,
references, and active-work records. Prepare the private classification and
exact-key request with a reason for each proposed deletion; do not ask the user
to label each object. Management/exclusive-writer evidence must be established
from real operating facts, never assumed from a bucket name or credential.
Unknown ownership, uncertain content, or an active reference means retain and
report the missing fact, with no upload or delete.

Use `object-storage-cleanup` for remote inventory, qualification, exact-key
planning, execution and resume. Local activity cleanup does not delete a remote
copy. Classify from creation purpose, contents, recorded work and present
references, never solely a filename, age or absence of links. The remote
inventory path can qualify eligible legacy files lacking receipts; that absence
is not a permanent unsupported state. Preserve necessary/shared data and active
work. Delete only approved exact keys and verify absence. An upload history is
not by itself a permanent preservation requirement. Keep uncertain effects and
use the original request's authenticated resume; never blindly repeat DELETE.

For a legacy inventory that needs content review, set
`include_content_samples: true` in the private inventory request. WOM then
verifies each complete remote object's SHA-256 while retaining at most the
first 4,096 bytes in the signed private inventory. Decode
`content_prefix_base64` only inside the private activity context and compare
it with creation purpose, work records and present references. The ordinary
command result deliberately does not echo content or remote keys. Work in
bounded selections of at most 4,096 objects. A prefix that is truncated,
binary, secret-bearing or ambiguous is not proof that the whole file is
disposable; hold it for further supported review rather than infer from its
name. Prepare the exact classification file yourself from evidence instead of
asking the user to label each object. Do not assert exclusive-writer control
without actual management evidence.

Use `object-storage-open` to open a temporary read link. Keep links and credential
values out of ordinary logs and zet bodies; opening is not a backup verification.

Upload, local-only bytes preservation (`object-storage-adopt-existing
--preserve-local-only`), offload, restore and activity cleanup retain an early
operation reference and a complete result artifact. After interruption inspect
that run and follow the saved plan/claim recovery route. Do not report all objects
preserved from a partial result, or re-upload a terminally verified object merely
because the parent command was interrupted.
