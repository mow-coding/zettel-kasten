# Archive infrastructure decision log — 2026-09-21, v0.4.36 (beta letter 168: no-dialog grants restored, the upload writer names its cause, delivered letters leave the archive)

Executing model: Claude Opus 5, solo and sequential for every unit, under
the user's standing approval; the read-only root-cause analysis of the
upload failure used ten bounded subagents (Opus 5) on the repository only.
No client archive, runtime, workspace, mirror or ledger was read or changed;
the client's letter was read from its feedback ledger; every fixture is
synthetic.

## Correction of a deviation from the 2026-09-17 decision

The user decided on 2026-09-17 that a work session's permission mode works
like the desktop apps' "allow all": `manual`, `limited`, and `allow_all`
with no dialog. v0.4.24 shipped that mode with an *implementer's* exclusion
list — fourteen, later eighteen, operation kinds (project update, remote
storage, recovery, deletion, session control) that always opened the dialog
"even in allow_all". The user never approved that list; the record of the
time says so ("the user never answered; my recommendation stands until he says
otherwise"), and the reply draft the user sent to the client described
`allow_all` as "세션 동안 창 없이". The client counted five dialogs under
allow_all in one day (letter 168 ⑥) and the user was put in a position he
had not chosen. v0.4.36 restores the decision:

* `ALWAYS_DIALOG_OPERATIONS` is empty; every operation kind is grantable;
  the grant covers an explicit original re-review as well.
* The only dialog-only ACTION is the grant itself (`set-permission-mode`),
  because a grant cannot mint, extend or replace itself — the same single
  switch the desktop apps ask for. The dry-run names it
  (`dialog_only_actions`, `dialog_only_reason`).
* The allow_all dialog line says what the mode covers ("업데이트·원격
  저장소·복구·삭제·세션 조작 포함, 이 대화에서는 승인 창 없음").

The deviation and its correction are recorded here as required by the
project's decision-record mandate.

## What letter 168 established

1. v0.4.35's update path worked exactly as designed (732 s, the fetch
   diagnosis and the affirmation); finalize closed 23 stale claims and the
   letter-164 scanner fix held.
2. The v0.4.33 upload writer died after the dialog at
   "exact-operation-preflight 0/3418" with
   `exact_human_approval_state_unknown`, no cause code, no journal, the
   claim left started; 3,417 objects were not uploaded.
3. Three store labels coexist; `store_setup_missing` said "register" when a
   registration existed under another label.
4. The finalize approve repeats the 550-second receipt scan.
5. `set-permission-mode --dry-run` refuses the approve request shape without
   naming the allowed keys.
6. Delivered-feedback archival (letter 164 ⑧) was asked a third time; the
   client answered the design questions.
7. The revise path needs `--feedback-ref` equal to the body's
   `feedback-body-sha256:<sha>`, which nothing said.

## Root cause of the upload failure (read-only analysis, ten agents)

The failure window is bracketed by the observation: the last progress line
is the in-claim re-plan's first publish, no heartbeat ever printed, no
checkpoint row was written. Two gates the dry-run never checked are the
tied top candidates: the manifest-index authority
(`archive_index_rebuild_required`, checked only inside the writer) and the
credential values (`env:` refs are read for the first time after the
dialog). Which one it was cannot be told from the client's result, because
the cause was dropped three times: the broker's cause-code allowlist did
not name the object-storage or exact-operation error classes; the upload
CLI clause forwarded only the outer code; the exact runner re-typed adapter
failures into three generic codes. The analysis record is kept with the
release scripts.

## Decisions

1. **Cause codes end to end.** The broker allowlist names
   `ObjectStorageUploadError`, `ObjectStoragePreservationError`,
   `ObjectStorageRestoreError` and `ExactOperationManifestError`; the exact
   runner carries the adapter's code as `cause_code` on its re-typed error;
   the upload envelope carries `cause_code`, `cause_stage`, an honest
   `effects_state` (`unknown` / `refused_before_effects`), the claim
   next steps and a `progress_summary`; `--progress-log` writes every
   suppressed publish to a JSONL file.
2. **Both silent gates move before the dialog.** The dry-run reports
   `manifest_index_authority` and `credential_refs_present` (env-ref
   presence, no value read); the approve refuses before the dialog with
   `archive_index_rebuild_required` or
   `object_storage_upload_credential_ref_unresolved` and reuses the one
   resolved transport for the approved write.
3. **A proven-no-effects failure closes its claim.** Every gate before the
   exact runner's first checkpoint (re-plan, approval binding, lock,
   control document, transport, index authority, ledger) and the runner's
   own preflight mark their failure `effects="none"`; the broker finalizes
   the claim as `failed` with the fixed cause and raises
   `exact_human_approval_writer_refused`. A failure after the first
   checkpoint keeps the started claim and the resume path, as before.
4. **Registered store labels.** `registered_store_refs` on a
   writer-unavailable dry-run and a next step that names the registration
   receipt's `account_ref` as the label to use.
5. **Delivered-feedback archival** (`operator-feedback-archive`), as the
   client designed it: an operator-designated folder outside the archive
   (path never echoed, only its SHA-256), copy → byte verification →
   content-free `archived` stub → removal, one id at a time, one receipt
   naming the claim; the body check reports `archived_stub` and the ledger
   counts `archived`. A grantable kind.
6. **Finalize re-scan.** The receipt inventory fingerprint (path, size,
   mtime per receipt) is bound into the plan digest; the approve re-scans
   only when the fingerprint changed, and the recheck before the first swap
   is the fingerprint too.
7. **Preview request shape.** `set-permission-mode --dry-run` accepts the
   approve request (`reviewer_claim` ignored) and a refusal names
   `required_keys` / `optional_keys`.
8. **Revise path.** `--create-draft-record` is the default
   (`--no-create-draft-record` opts out); step 1 of the announced path says
   the ref must equal the body's `feedback-body-sha256:<sha>`.
9. **Coverage manifest.** The five pending session-ref rows are
   `session_integrated` through the `environment` route (the broker resolves
   the grant from the process refs; every kind is grantable), and the new
   command is classified the same way.

## Not done

The update's grant coverage is asserted at the broker with a synthetic
project-update context; the full Windows updater transaction under a grant
is the client's run to confirm. `max_writes`, per-session / bulk revoke,
select-all for `git-backup-reconcile-plan`, a reviewed re-PUT and 8b move to
v0.4.37.
