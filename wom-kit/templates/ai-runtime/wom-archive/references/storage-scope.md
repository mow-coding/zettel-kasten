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
  desktop apps' keychain: the human adds two generic credentials (access key,
  secret key) in 자격 증명 관리자 and the request names them exactly as
  `credential-manager:<target>`. An `env:` ref ends with its process. If a
  preview reports `credential_refs_state: unresolved`, stop; for an unfinished
  `activity-cleanup`, rerun `--reconcile --dry-run` with
  `--rebind-access-key-id-ref` and `--rebind-secret-access-key-ref`, then the
  matching `--approve`. Completed items are not reprocessed; never put a key in
  chat, a file, or a command line.

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

A filename, age or ignore rule alone is not disposal evidence. Preserve unique
work, secret configuration, Git history and other activities' dependencies.
Temporary files cannot silently use `preserve`; meaningful intermediate
evidence needs the appropriate role and reason. A valid full-access grant
covers the official child operations without additional approval windows.
Do not delete already-uploaded remote temporary objects through local cleanup.

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
