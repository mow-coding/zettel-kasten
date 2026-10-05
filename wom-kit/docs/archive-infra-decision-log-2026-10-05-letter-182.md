# Archive infra decision log: letter 182 (2026-10-05)

Status: implemented for v0.4.63 under the owner's standing instruction
("이거 보고 바로 작업 시작해"). Executing AI: Claude Fable 5.1. The design
choices below marked "delegated" were made by the worker's recommendation
under the owner's 2026-09-25 design delegation; they were not individually
approved.

Letter 182 came from v0.4.62. Two activity folders still held five PDFs that
are hard links of each other (one file, two names: ten paths), and two
configuration files. `activity-cleanup --dry-run` on one representative path
was refused with `activity_cleanup_regular_single_link_file_required`, and
the person had to ask several times whether the folders could be deleted.

## A. Hard-link groups

Reproduced with a synthetic file linked into folders A and B: the plan
refused the path outright, so there was no supported route. The refusal was
correct for a file that is also linked outside the selected folders (deleting
one name would silently leave, or silently share, the body), but it was also
applied when every link is inside the selected scope.

Measured on NTFS (synthetic probe): the link count of a file drops from N to
N-1 when one name is marked for deletion, a cancelled mark restores N, and
the remaining name keeps its bytes and its alternate data streams.

Decisions:

1. Every link is its own item. A multi-link file is plannable only when all
   of its links are selected items of the same request with the same role and
   disposition. One selected path of a larger group is a named blocker
   (`activity_cleanup_hardlink_not_fully_selected`); the plan reports the
   group's link count, how many links are selected, how many unselected links
   are inside the selected folders and how many are outside them. Paths
   outside the selected folders are counted, never listed.
2. A link outside the selected folders stays held. WOM does not search other
   folders for it and no flag overrides it (delegated).
3. The body is preserved once: the items share one content address, so the
   upload and the receipt happen once and each item is verified against it.
4. The bound delete proves the expected link count instead of assuming one:
   the count is the number of approved sibling paths that still exist with
   the same file identity, checked before the delete mark and as that count
   minus one after it. A link created after planning changes the count and
   both names are retained (`activity_cleanup_file_changed`).
5. Alternate data streams are inventoried and preserved per item as before;
   the stream check after a delete expects the count minus one.
6. An interrupted run resumes: a name that is already gone lowers the
   expected count for its siblings.
7. Reclaimed space counts each file once, when its last link is removed
   (`newly_deleted_distinct_file_count`, `newly_deleted_path_count`).

## B. Secret configuration files (delegated)

The helper had no role for a real secret file: preserving it would upload a
secret, and discarding it as "temporary" would be a false classification.

1. New role `secret_config`. It is never uploaded
   (`activity_cleanup_secret_config_is_never_uploaded`).
2. `retain` is always allowed. `discard` requires `discard_intent: true` and
   `secret_values_kept_elsewhere: true`, which the helper sets only after the
   person confirms it for that file
   (`activity_cleanup_secret_config_discard_requires_person_confirmation`).
   WOM cannot verify the statement; it records that it was made.
3. An example configuration without secret values is an ordinary `source`.
   WOM does not decide which is which from the file name.
4. No unconditional deletion and no content scanning for secrets.

## C. What "done" means

The result and the status carry `selected_items_complete` and `folders_empty`
as separate answers, `plain_summary` sentences, and leftover counts as paths
and as distinct files (`remaining_path_count`,
`remaining_distinct_file_count`, hard-linked paths and files, possible secret
configuration). `whole_folder_cleanup_complete` is true only when both hold.
The operator guidance tells the helper to report local leftovers, online
publication and the private backup as three different things.

## D. Who does what

The guidance says: the helper lists the links, classifies and runs the plan;
the person confirms only where a human statement is required (a secret file's
values kept elsewhere, a link outside the activity). If something is
unsupported the helper records one reproduction and waits; it does not push
retries or work around the check by copying, unlinking or replacing files.

## Boundaries

Verified with synthetic files on Windows (NTFS) and the real CLI, and the
non-Windows path on Linux. The customer's ten paths and two configuration
files are not verified until the customer runs v0.4.63.
