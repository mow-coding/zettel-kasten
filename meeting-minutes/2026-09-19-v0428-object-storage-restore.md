# v0.4.28 object-storage restore (OB-01 / OB-03) — implementation record

OB rows, 2026-09-04 plan, slipped from v0.4.23: OB-01/OB-02/OB-03 were decided
on 2026-09-04 (decision 6) and scheduled for v0.4.23; the v0.4.22–v0.4.27
update-failure and dialog hotfix train pushed them aside without a recorded
decision. On 2026-09-19 the user asked about the "upload, then clean up
local" feature, corrected the maintainer's first (wrong) answer that it
needed a new design, and confirmed building it ("그래 임마... 이거 진작에
됐어야 하는건데"). Order agreed: restore first (v0.4.28), delete second
(v0.4.29).

Date: 2026-09-19 (Korea Standard Time)
Executing model: Claude Opus 5 (high); a bounded read-only Ultracode workflow
(5 mapping agents + 1 design synthesis, no writes) produced the code map and a
design proposal that the maintainer compared against its own; every write,
test and release step is solo and sequential.
Branch/worktree: `claude/v0428-object-storage-restore` in
`zettel-kasten-v0428-work` from main `92c3b7dc`.

## Scope

- Unit A — transport primitive. `ObjectStorageTransport.get_object(key,
  sink_path, expected_size, expected_sha256)` on the protocol, `NullTransport`
  and `_S3CompatibleTransport`; `_default_urllib_sender` streams a restore GET
  into a create-only sink (O_EXCL, bounded, fsync) and returns the same digest /
  size / completeness evidence plus `sink_written`; `_dispatch` forwards the two
  sink keywords only when set. Live sender idle timeout 120 s
  (`OBJECT_STORAGE_HTTP_IDLE_TIMEOUT_SECONDS`).
- Unit B — approval kind `object_storage_bytes_restore` ("오브제 원격 바이트
  되찾기", "바이트 되찾기"), always-dialog.
- Unit C — module `object_storage_restore.py` (plan → dry-run document; exact
  operation manifest with one receipt item per object plus one manifest
  projection item; writer fetches, verifies twice, places no-replace, records;
  verifier re-derives from receipts and disk; control document, resume,
  verify), CLI `object-storage-restore` (alias `objet-storage-restore`) with
  `--verify-only`, `--only`, `--max-objects`, resume flags; generalized
  `_object_storage_live_transport_factory` shared with preservation.
- Unit D — `resolve-objet-ref` state `remote_verified_local_absent`,
  `restore_workflow`, per-candidate `remote_verified_by_wom_kit`.
- Unit E — pins: CLI 577→579 (+1 command +1 alias), inventory 317/259/576/56/274
  → 318/260/578/57/275, packaged resources 169→170 (new receipt schema
  `object-storage-restore-receipt-v0.1`), writer-session coverage manifest row
  (pending, target v0.4.30) and its eight release-docs pins 56→57 / 29→30,
  doc count sentences.
- Unit F — docs: contract restore section and sender note, sovereignty doc
  (restore direction, decision-6 exception), capability-matrix row, register
  rows OB-01/OB-03 (development verified, "slipped from v0.4.23") and OB-02
  (v0.4.29 plan), decision log
  `archive-infra-decision-log-2026-09-19-v0428-v0429-object-restore-offload.md`.

## Decisions taken while building (beyond the decision log)

- Sinks live under `profiles/local/exact-operations/restore-sinks/<manifest16>/`
  rather than beside the destination, so a partial download never sits inside
  `objects/sha256/` where inventories would see it; the no-replace move makes
  the capture race safe without holding the manifest lock during the download.
- No provider-call journal or ledger: a GET has no provider side effect; the
  exact-operation checkpoint store plus the per-object receipt are the resume
  surface. A crash after the move but before the receipt is recovered from
  disk (`already_present_verified`, no second GET).
- The manifest projection's post state is "every restored object of the batch
  has an active local location"; review-required objects stay without one, so
  a corrupt remote copy cannot mint a local location.
- `--verify-only` receipts (`remote_verified`) are the OB-01 general workflow;
  they cost a full download per object and are bounded by `--only` /
  `--max-objects`.
- The corrected answer to the user: the feature was already decided and
  scheduled; the record now says so in the register rows and this file.

## Verification

- `test_v0428_object_storage_restore` (21): transport primitive (7 incl. the
  real sender with a fake opener and the idle timeout), plan selection
  (remote sources, already-present, conflict, declared-only, other store,
  preservation receipt, offloaded, verify-only, --only, --max-objects, setup
  evidence), execution (restore + projection + Doctor deep, mismatch/absent
  review, transport trouble resume without re-download, crash after move,
  local conflict + stale sink, verify-only), resolver, packaged schema, CLI
  (dry-run → approve through the live transport seam with a fake sender and
  fake dialog, cancel, usage codes).
- Cohorts rerun green: object-storage preservation / adoption / setup
  registration / manifest-writer index lifecycle (transport seam), exact
  dialog + permission modes + client follow-ups (approval kind), resolver
  tests in test_cli / objet rediscovery / MCP server, and the pin tests
  (predecessor surfaces, private index gate, v0.4.1 and v0.4.20–v0.4.27
  release docs, coverage gate, capability matrix docs).

## Boundary

Synthetic archives only; the client workspace was not read or changed; no
provider was called; no credential value was read. Client acceptance of
OB-01/OB-03 waits for the client's own run on v0.4.28.
