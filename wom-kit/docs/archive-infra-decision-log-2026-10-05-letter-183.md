# Archive infra decision log: letter 183 (2026-10-05)

Status: implemented for v0.4.64 under the owner's standing instruction
("보고 바로 작업 시작해"). Executing AI: Claude Fable 5.1. The design choices
below were made by the worker's recommendation under the owner's 2026-09-25
design delegation; they were not individually approved.

Letter 183 came from v0.4.63. The hard-link support worked: five PDFs under
ten paths were cleaned (9 in the first run, the last through reconcile). The
run still ended `partial` with exit 1, because four of the five listed
folders held empty subfolders. One folder kept 64 empty subfolders, the other
2,642 and two small configuration files. The recovery text read as if file
items were unfinished, no request could address folders only, and a `.git`
that the earlier cleanup had emptied blocked every later plan.

## A. Folder removal is its own outcome (request 가)

Reproduced with the customer's shape (one file linked into two folders, each
with an empty subtree, both folders listed in `remove_empty_directories`):
files 2 of 2, both folders `retained_nonempty_or_changed`, `partial`.

1. `folders_empty` keeps its meaning (no files) and is also exposed as
   `folders_contain_no_files`; `folders_removed`, the count of selected
   folders that still exist and of their subfolders are separate facts.
2. Each listed directory that is kept carries a code: `contains_subdirectory`,
   `contains_file_or_link`, `directory_changed_since_plan`,
   `directory_state_unavailable`.
3. The result has `folder_outcome` and, when every file is finished and only
   folders are left, `state_detail:
   selected_items_complete_folder_removal_unfinished`. The exit code stays 1:
   a folder the request asked to remove still exists.
4. `operation-control` recovery guidance for that case says the files are
   finished and names the folder count; the reconcile guidance stays for real
   unfinished items and for results of older versions.
5. Files kept on purpose (`retain`, including protected secret configuration)
   are counted and described as a finished state.

## B. Folder-only closeout (request 나)

1. `items` may be empty when the request names `remove_empty_directories` or
   the new `remove_empty_directory_trees`. An existing activity's intent is
   immutable, so the closeout is a new request with a new `activity_id`.
2. `remove_empty_directory_trees` takes exact directories inside the roots (a
   root itself is allowed; trees must not overlap; at most 64). At plan time
   every folder of the tree is recorded with its identity. At execution the
   folders are visited deepest first and each is removed by the existing
   bound empty-directory delete only if it is the planned folder and empty.
3. A folder that holds a file, link or reparse point at any depth is kept
   with its parents. That is the stated contract and not a failure. A folder
   that changed, appeared after the plan, or cannot be checked is not removed;
   a changed or unverifiable planned folder makes the run `partial`.
4. Junctions and links are never followed or removed.
5. No file is uploaded, moved, restored or deleted by the folder part.
6. The approval binding of a request with items is unchanged. A request
   without items binds its exact directories and trees instead.
7. The preview gives counts per tree and never a path; the exact list is in
   the private plan.

## C. An emptied `.git` (request 다)

A `.git` directory with no file, link or reparse point at any depth is
reported as `{"repository": false, "empty_git_residue": true}` and treated as
ordinary empty folders. Any content keeps the existing Git checks, including
the refusal when Git cannot read it.

## D. Time and state wording (request 라)

`measurements.plain_time_summary` states the approval wait, the wait for
another writer, the processing time and its largest non-overlapping parts,
and that the command has ended. No new measurement was added, and the
customer's first run (about 19 minutes for ten paths) is not explained by
this release.

## E. Session refs before a write (request 마)

The customer's helper did not export the conversation's three routing refs in
new processes, so approval windows opened although the grant was valid.

1. An activity-cleanup preview carries `caller_session_context` (presence
   only, never a value).
2. A result whose approval window opened while the refs were missing or
   incomplete carries `caller_session_context` with
   `dialog_shown_without_session_refs`. It does not claim that a grant exists
   or expired. A refusal reason, when there is one, takes precedence.
3. A write is not refused for missing refs: a conversation without a session
   may still be approved through the window.
4. The guidance tells the helper to check before every `--approve` and where
   in its own conversation the refs are (also in tool-call inputs).

## F. Secret configuration the owner cannot vouch for (request 바)

Guidance only. The file stays `retain`. The helper names the variables, never
the values, and explains that a provider listing a name does not prove the
value can be read back or equals the local one. The file may be discarded
only after the person saves the values somewhere readable and says so.

## Boundaries

- The old-cleanup boundary of letter 181 (968 of 1,070 items whose Windows
  alternate-stream state cannot be proven) is unchanged.
- Verified with synthetic files on Windows (NTFS) and the real CLI, and the
  plan path on Linux. The customer's folders are not verified.
