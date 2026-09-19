# v0.4.29 object-storage offload (OB-02) — implementation record

OB rows, 2026-09-04 plan, slipped from v0.4.23: OB-02 is the second half of the
feature the user and the client asked for since the first uploads (decision
6, 2026-09-04). v0.4.28 built the way back; v0.4.29 builds the way out on top
of it, in the order the user agreed ("되찾기 먼저, 삭제 다음").

Date: 2026-09-19 (Korea Standard Time)
Executing model: Claude Opus 5 (high); a bounded read-only Ultracode workflow
(4 mapping agents, 1 design synthesis, 3 adversarial verifiers; no writes)
produced the code map and a design that the maintainer compared with its own
implementation. The verifiers refuted the synthesised design on five points
that also applied to the first implementation and were fixed before commit:
the source token must not hash the local location the projection flips; the
proof marker must be bound to the approved execution; the bound-delete
primitive is Windows-only; a torn marker must not wedge an item; bytes that
reappear must not fail the verifier. Every write, test and release step is
solo and sequential.
Branch/worktree: `claude/v0429-object-storage-offload-wip` in
`zettel-kasten-v0429-work`, branched from the v0.4.28 candidate; the release
branch is re-created from main after v0.4.28 merges.

## Scope

- Unit A — Doctor: `availability: offloaded` on a local location is
  `local_object_offloaded` INFO (a strict run stays green; a new
  `offloaded_local_reference_count` in the byte summary; never counted as
  unresolved); bytes present under an offloaded location warn
  `local_object_offloaded_but_present` (restore `--only` reactivates the row).
  The path is checked lexically because the shard directory may be absent.
- Unit B — backup-evidence: `offloaded_local_location_object_count` and
  `remote_only_object_count`; doc paragraph.
- Unit C — staged-cleanup-check: an offloaded objet's staged copy is
  `deferred` with `objet_bytes_offloaded_remote_only_restore_before_cleanup`
  (registered in operation_control); the strict canonical predicate accepts an
  offloaded local location (the bytes check still decides preservation).
- Unit D — the writer `object_storage_offload.py` and CLI
  `object-storage-offload` (alias `objet-storage-offload`): retention
  evidence scan of every inbox draft (objet tokens in body and frontmatter;
  private fidelity receipts by `creation_plan_sha256`), eligibility predicates
  with counted exclusions, plan/control/resume/verify on the restore template,
  per-object write = local re-hash → full-GET re-hash → local re-hash +
  identity → execution-bound atomic proof marker → handle-bound delete →
  receipt → marker discard; one projection flipping local locations to
  `offloaded`. Approval kind `object_storage_bytes_offload`, always-dialog.
- Readers: `resolve-objet-ref` `local_offloaded` + text label; the upload
  planner's `local_offloaded` row flag and `offloaded_object_skipped_restore_before_upload`
  warning instead of the whole-store blocker.
- Unit E — pins: CLI 579→581, inventory 318/260/578/57/275 →
  319/261/580/58/276, packaged resources 170→171 (receipt schema), coverage
  manifest 57→58 / pending 30→31 (nine release-docs pins + gate + create-draft
  session + notion backfill CLI), startup progress list.
- Unit F — docs: contract offload section, sovereignty doc, matrix row,
  register OB-02 (development verified), decision-log amendment (dated, not a
  rewrite).

## Decisions taken while building

- Restore keeps both remote sources (wom_uploaded location, preservation
  receipt); offload accepts only wom_uploaded locations.
- Provenance allowlist for offload candidates (capture sources only) rather
  than changing the three snapshot writers that append a record when no
  available location exists; those writers are a carried item.
- No sink for the proof: the remote-query adapter's full GET re-hash; the
  marker (not a copy of the bytes) is the journal.
- Windows-only apply, following the codebase's existing bound-delete policy;
  the execution and CLI cohorts are skipped elsewhere and the plan test
  asserts the platform blocker.
- Defaults: `--min-age-days 30`, `--min-size-bytes 0`; `--only` bypasses the
  filters, never the predicates.

## Verification

- `test_v0429_object_storage_offload` (18): readers (Doctor INFO/WARN + strict,
  backup-evidence counters, staged-cleanup deferral), plan predicates and
  exclusion counters incl. preservation-only and provenance exclusions,
  unreadable fidelity receipt blocks the plan, offload → readers → restore
  round trip on the fake archive with Doctor `--strict` green at both ends,
  remote mismatch/absence keeps local bytes, crash after delete resumes from
  the marker without a second download, foreign-execution marker not
  honoured, torn marker discarded, reappeared bytes keep the row available,
  bytes gone without a marker refused, transport trouble resume + a new draft
  reference stops the resume, CLI dry-run → approve through the live seam
  (HEAD then GET), cancel removes nothing, usage codes.
- Reran green: Doctor cohorts, staged-cleanup/backup-evidence/doctor test_cli
  subsets, restore cohort, approval dialog/permission cohorts, every pin cohort.

## Carried

- Snapshot writers (`canonical_zet_before_revision`, `..._before_title_remap`,
  activity-group before-snapshots) and `objet_capture re_materialize` /
  tiro recovery still ignore the offloaded state (excluded from offload by the
  allowlist; re-materialised bytes are reported by Doctor and reactivated by
  restore).
- A POSIX bound delete.
- `create-draft` from an offloaded fidelity source fails with the existing
  `source_fidelity_object_missing_or_unsafe`; restore first.
