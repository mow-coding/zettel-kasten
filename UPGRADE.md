# Upgrade Guide

[한국어 업그레이드 가이드](UPGRADE.ko.md)

This guide explains how to move between public `zettel-kasten` / `zet` versions.

The project is versioned because archive rules, zettel metadata, object manifests, provenance records, and future `ZET` sharing envelopes must be understandable across users and tools.

## Quick Rule

```text
PATCH upgrade -> documentation, validation, or compatible fixes
MINOR upgrade -> compatible new features or optional fields
MAJOR upgrade -> breaking protocol/schema changes
```

Before upgrading a real archive:

1. Read the target version note in `wom-kit/docs/releases/`.
2. Back up the private archive repository and object manifests.
3. Run `archive doctor --strict`.
4. Run migration commands in dry-run mode first when available.
5. Commit private archive changes only after reviewing generated receipts.

The archive should never silently rewrite memory.

## v0.4.18 Terminal Original Cleanup

Install the exact public wheel only after the matching release and asset exist.
Use a new external CPython 3.12 environment so the real `python.exe -m pip`
records the wheel hash in installed PEP 610 metadata.

```powershell
$womBootstrapNonce = [guid]::NewGuid().ToString("N")
$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\bootstrap-v0418-$womBootstrapNonce"
if (Test-Path -LiteralPath $womBootstrapRoot) {
  throw "WOM bootstrap path must be new."
}
py -3.12 -m venv $womBootstrapRoot
$womBootstrapPython = (Get-Item -LiteralPath (Join-Path $womBootstrapRoot "Scripts\python.exe")).FullName
& $womBootstrapPython -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.18/wom_kit-0.4.18-py3-none-any.whl"
& "$womBootstrapRoot\Scripts\archive.exe" --version
```

Require exactly `archive 0.4.18` from a new process. Publishing or installing
the wheel changes no client archive, project runtime, or version pin. A client
separately chooses and approves any project update.

Approved project-update mutation, same-version repair, and mutation-bearing
resume remain Windows-only. POSIX supports preview and read-only inspection;
those mutation paths fail closed without writing.

v0.4.18 finishes one more shape without asking the person for anything. If an
earlier update reached `completed` but its transaction directory still exists
with its cleanup plan inside, and the project has since moved to another
version, dry-run and approval return `terminal_cleanup_required` with the
basis `exact_terminal_transaction_cleanup_requires_resume`. The identifier-free
resume below then re-authenticates the original approval claim from the
archive, cleans only that private transaction directory into one canonical
proof, and returns `terminal_transaction_cleanup_completed` with
`update_completed: false` and `past_update_success_attributed: false`. It does
not change source, runtime, pin, or archive content and does not open a new
decision. Run a fresh preview afterwards and request one new approval only if
that preview is ready. If the same resume fails again, the redacted `--output`
artifact now names one fixed inner `cause_code` and `cause_stage`; send that
content-free result to development instead of retrying.

Fresh dry-run and approval now share one read-only terminal-cleanup preflight.
If either returns `project_version_update_terminal_cleanup_required`, do not
request another approval and do not inspect or edit private control files.
Keep other writers for the same project stopped and use the identifier-free
resume command below. WOM verifies and compacts only exact terminal abort
history, preserves canonical proof history, and changes no project-domain file.
After recovery finishes, run a new dry-run and request one fresh approval only
if that new preview is ready.

If the result is
`project_version_update_terminal_cleanup_outcome_unknown`, stop. Do not loop
resume, delete a lock, edit a pin, or remove transaction, tombstone, or proof
evidence. Preserve the structured result for development review.

The recovery result can show an empty `files_written` list while still reporting
completed private control-history work. `files_written_scope:
project_domain_only` limits that list to project-domain files. Read
`terminal_abort_histories_compacted`, `terminal_abort_history_compaction_state`,
and the content-free `effect_summary` together; `partial` or `incomplete` means
stop and preserve the result rather than retrying or deleting evidence.

For an interrupted approved update or exact terminal control history, keep
other project writers stopped and use the identifier-free resume path:

```powershell
& "$womBootstrapRoot\Scripts\archive.exe" project-version-update <project-or-archive-root> `
  --resume `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

Approved and resumed updates create a private project-scoped output when
`--output` is omitted before binding. Once terminal delivery is pending, do not
supply another output: preserve the exact bound output and run identifier-free
`--resume`. WOM verifies the immutable terminal journal and moves the same
handoff through `active`, `display-pending`, and hash-named `consumed` states.
It may print the identical result again after a crash, but never reruns the
domain writer. A consumed capsule is history, not a replay candidate, and
delivery acknowledgement does not prove that a person or model saw stdout.

One complete legacy cleanup tombstone is recoverable only after exact
validation. Proof-only state returns `no_resumable_project_update`, attributes
no past success, and requires a fresh preview and approval for a new update.
Partial, malformed, mixed, or unsafe residue remains
`terminal_cleanup_outcome_unknown`; do not delete or hand-edit it. The returned
`terminal_finalization` object distinguishes authenticated update truth from
transaction cleanup, service close, Git-runner close, and durable-result
handoff truth. See the [v0.4.16 release note](wom-kit/docs/releases/v0.4.16.md).

## v0.4.15 Authenticated Project Update Recovery

Install the exact public wheel only after the matching release and asset exist.
Use a dedicated external CPython 3.12 environment; a user-scoped `uv tool`
installation whose metadata omits the wheel hash is not project-updater supply
evidence.

```powershell
$womBootstrapNonce = [guid]::NewGuid().ToString("N")
$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\bootstrap-v0415-$womBootstrapNonce"
if (Test-Path -LiteralPath $womBootstrapRoot) {
  throw "WOM bootstrap path must be new."
}
py -3.12 -m venv $womBootstrapRoot
$womBootstrapPython = (Get-Item -LiteralPath (Join-Path $womBootstrapRoot "Scripts\python.exe")).FullName
& $womBootstrapPython -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.15/wom_kit-0.4.15-py3-none-any.whl"
& "$womBootstrapRoot\Scripts\archive.exe" --version
```

Require exactly `archive 0.4.15` from a new process. If a previous approved
project update was hard-interrupted, keep all other project writers paused and
resume from the exact bootstrap:

```powershell
& "$womBootstrapRoot\Scripts\archive.exe" project-version-update <project-or-archive-root> `
  --resume `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

The normal resume requires no caller-supplied `--target`, `--transaction-ref`,
`--approval-id`, or `--reviewed-by`. WOM restores those bindings from the live
lock and authenticated sealed plan, requires exactly one checkpoint-valid
claim, and opens no second native decision. Never delete the lock or hand-edit
the pin. After success, start a new project-launcher process and verify
alignment before approved zet draft or other ordinary write work.

This v0.4.15 recovery guarantee is bounded to a live `version-update.lock` or
the exact lockless unlock tail while the original transaction directory still
exists. Its first unsupported boundary is after `completed`, once the original
transaction directory has been successfully renamed to a terminal cleanup
tombstone. A tombstone or cleanup proof is not authenticated outcome or cleanup
authority: v0.4.15 reports `terminal_cleanup_outcome_unknown` with a nonzero
exit and does not infer success, failure, or cancellation, automatically retry,
or delete that evidence. A full authenticated terminal handoff and terminal
cleanup outcome reconstruction remain a v0.4.16 follow-up.

While recovery is required, only an exact-approved create-only operator
feedback body may be appended. Existing feedback revision or supersession,
metadata, resolved or delivered state, and every other writer remain blocked;
the `version-update.lock` bytes remain unchanged. v0.4.15 requires no public
archive-format migration. See the
[v0.4.15 release note](wom-kit/docs/releases/v0.4.15.md).

## v0.4.14 Reference-Aware Local Recovery And Safer Decisions

Install the exact public wheel only after the matching release and asset exist:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.14/wom_kit-0.4.14-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.14` from a new process. A shared PATH executable is
not proof that the intended client project was updated. Use the project-local
launcher only after the separate reviewed `project-version-update` succeeds.

v0.4.14 does not require a public archive-format migration. It corrects local
recovery and human viewing:

- `external-locator-record --all-markup-receipts --dry-run` discovers and
  verifies the fixed historical receipt set itself. It preserves exact reviewed
  references, classifies partial evidence, and proposes one private ledger; it
  does not restore complete old bodies over valid current content.
- identifier-title recovery may take the private mirror folder, but only an
  exact unambiguous Markdown/index pair is accepted;
- supported native decisions may show a bounded local target clue only when the
  plan already binds the exact current zet bytes. Unsafe clues are omitted;
- complete body-bearing CLI text output uses a display-only Markdown projection;
  structured JSON/service/MCP body reads stay canonical, and bounded pages
  remain canonical source while deferring projection.

The AI runs and verifies the complete dry-run. The person does not count rows,
copy receipt paths, or compare hashes; they review the plain operation and
choose run or cancel. Publishing or installing the release performs no client
recovery. A client result requires that project's separately approved run,
durable receipt, and independent verification. See the
[v0.4.14 release note](wom-kit/docs/releases/v0.4.14.md).

## v0.4.13 Exact Setup Evidence And Create-Only Byte Preservation

Install the exact public wheel only after the matching release and asset exist:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.13/wom_kit-0.4.13-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.13` from a new process. A shared PATH executable is
not proof that the intended client project was updated. Use the project-local
launcher after the separate reviewed `project-version-update` succeeds.

v0.4.13 does not require a public archive-format migration. It tightens two
existing object-storage paths:

- setup readiness now trusts the canonical exact binding and receipt first;
  malformed, orphaned, changing, case-colliding, and cross-provider evidence
  fails closed without echoing private setup values;
- `object-storage-adopt-existing --preserve-local-only` publishes remote bytes
  create-only for single and multipart objects and independently verifies them
  with HEAD plus a complete GET rehash.

The AI should run the dry-run, verify the complete machine evidence, and show
the person only the plain operation effect. The person chooses run or cancel;
they do not count records or compare hashes. A live provider call occurs only
after the client explicitly authorizes the exact operation in its intended
project runtime. Publishing, installing, or planning the release performs no
upload.

A successful item is classified as `bytes_preserved` or
`already_remote_verified`. A proven conflicting remote object becomes
`review_required` without overwrite. Unavailable or uncertain provider
evidence remains resumable and has no terminal success receipt. None of these
states adds a formal-adoption manifest location. See the
[v0.4.13 release note](wom-kit/docs/releases/v0.4.13.md) and the
[object-storage execution contract](wom-kit/docs/object-storage-adapter-execution-contract.md).

## v0.4.12 Generation-Bound Link and Index Authority

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.12/wom_kit-0.4.12-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.12` from a new process. Installation alone changes
no client archive. After the project runtime update, the AI—not the person—must
bring the archive projection to an explicit healthy state:

```powershell
.\.zettel-kasten\bin\archive.cmd index <archive-root> --progress --format json
.\.zettel-kasten\bin\archive.cmd index-health <archive-root> --dry-run --progress --format json
```

WOM verifies the resulting counts, hashes, generation, and health evidence. The
person decides only whether to run the plainly described operation; they do not
count files, compare digests, or reconstruct index state.

`zettel-objet-link` planning and apply now bind the current SQLite generation,
one exact target row, unique zet and Objet identities, the manifest descriptor,
and stable file evidence. An exact existing link returns deterministic
`already_present` without approval or a write. zet writers begin one durable
same-generation dirty intent before the first canonical write and either seal
the exact batch delta in that generation or remain dirty with
`archive_index_rebuild_required`. A missing or stale index fails before
approval, canonical mutation, checkpoints, or receipts; an authenticated
same-generation dirty resume remains available.

The parser-derived current inventory is 47 approval-available, 67 fixed-closed,
and 201 not-exposed paths. In particular,
`zet-revision-restore-proposal-from-snapshot --approve` and the standalone
command path `derive-text capture --approve` remain fixed closed before private
inputs are read. The paired derived-text work inside the separately approved
`objet-capture-batch` route is not that command. Dry-run previews and historical
evidence remain available. See the
[v0.4.12 release note](wom-kit/docs/releases/v0.4.12.md).

## v0.4.11 Runtime Truth and Deep Verification

Install only after the matching public Release lists the exact wheel and its
exact-scale Doctor evidence has passed:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.11/wom_kit-0.4.11-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.11` from a new process. This global command is a
bootstrap, not proof that a client project has been updated. Use it only to run
the reviewed `project-version-update`, then invoke ordinary project work through
that project's `.zettel-kasten/bin/archive.cmd`. v0.4.11 checks the fresh
installed payload, module inventory, launcher, current process, project pin,
and running version together; a computer-wide command with the same version
number is not accepted as the project runtime.

Deep Doctor remains the default and hashes every unique objet once. Choose
Operational mode only when a faster structural inspection is sufficient; its
result explicitly says that full byte integrity is not verified, and it cannot
be used with `--strict`. A mint-lifecycle SHA mismatch is softened only when
one exact chronological direct-receipt chain reaches the current bytes.
Local-recovery state evidence without bound completion chronology remains an
ERROR that needs review.

Native decisions now show the local zet, draft, edge, or objet target using WOM
terminology without copying that private preview into public output or durable
receipts. The document read surface escapes accidental range tildes and
unmatched emphasis only in its display projection; canonical zet bytes remain
unchanged. Read-only revision/discard previews do not grant write authority,
and fixed-closed writers remain closed.

The repeated full-tree `zettel-objet-link` and incremental index architecture
remain v0.4.12 work. v0.4.11 does not speed that path by removing identity,
duplicate-ID, watcher, or stable-point checks. Publishing, installing, or
testing this release does not modify a client archive; the client decides when
to update and when to run project-scoped checks. See the
[v0.4.11 release note](wom-kit/docs/releases/v0.4.11.md).

## v0.4.10 Bounded Batch Intake and Capture

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.10/wom_kit-0.4.10-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.10` from a new process. Installation changes no
archive. The client runs the project-scoped batch commands in the intended
project runtime; development does not replace a computer-wide executable or
perform client recovery on the client's behalf.

For 1–1,000 reviewed local items, v0.4.10 reduces the work to two human
decisions. `source-intake-batch` records the complete intake batch and generates
the exact capture request. Its successful output returns the content-free
source-intake execution SHA-256 used by `objet-capture-batch`; WOM derives the
request path and revalidates the authenticated completion chain automatically.
The person does not count files, compare hashes, or reconstruct receipt paths.
Every batch source must already be archive-relative so that this handoff can be
generated. A batch containing an external source stops before approval; use the
unchanged v0.4.9 single-file metadata-intake route when that is the intended
operation.

If intake stops after approval, rerun the exact unchanged command and reviewer
with `--resume`; do not find or copy an approval id or execution digest. WOM
authenticates and resumes only one unambiguous candidate, and blocks a resume
from the wrong project runtime. If capture stops or only partly converges, do
not automatically retry it or reuse the old approval. Run a fresh exact capture
dry-run against current state, review its plain-language batch effect, and make
a new native decision. Existing verified objects converge without duplicate
rows.

The 1,000-item synthetic planning gate completed in 42.926 seconds and retained
early status plus bounded heartbeats. Remaining per-item Windows
path/configuration reconstruction is deferred to v0.4.11; v0.4.10 does not
claim that cost is optimized. See the
[v0.4.10 release note](wom-kit/docs/releases/v0.4.10.md).

## v0.4.9 Finish the Safe Single-File Path

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.9/wom_kit-0.4.9-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.9` from a new process. Installation changes no
archive. For one reviewed local file, v0.4.9 can record exact intake evidence,
create an exact capture selection, and preserve the selected bytes through
three separate native decisions. Doctor now reports content-free progress by
default, invalidates object-manifest findings when that input changes during
the run, and distinguishes a runnable suggested dry-run from a still-closed
approval mode. Object-storage setup now requires a resolved profile id and
does not pretend to create a profile registry.

Matching receipt bytes that existed before this exact writer ran are not proof
of a completed approval. WOM leaves them unchanged and reports that completion
evidence is required instead of claiming the intake chain succeeded.

`--progress-log` now requires a new file outside the archive root. Choose a
fresh external log path for each run; WOM rejects an existing file or any path
inside the archive before Doctor starts. This prevents an observational log
or hardlink alias from overwriting archive evidence. WOM retains the original
exclusive handle for the run, so replacing the visible path later cannot
redirect subsequent progress events.

Doctor `--output` likewise requires a new archive-relative file. It never
overwrites an existing archive file, including an existing hardlink alias.

Batch intake/capture remains fixed closed, and heartbeat is not proof that the
reported doctor runtime has been optimized. See the
[v0.4.9 release note](wom-kit/docs/releases/v0.4.9.md).

## v0.4.8 Integrity Recovery Without Guesswork

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.8/wom_kit-0.4.8-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.8` from a new process. Installing the wheel does
not change an archive. v0.4.8 makes interrupted exact operations explain their
durable state and find one unambiguous resume or revert control automatically.
It also narrows title and marker recovery to the correct source field, rejects
unsafe locator sidecars, creates capture selections only from existing intake
evidence, records local object-storage setup without contacting a provider,
and reconciles only strictly proven duplicate pairs without losing either
definition.

Locator occurrence anchors are still diagnostic hints, not recovery proof;
v0.4.8 has no verified occurrence-recovery receipt contract. When a supported
field recovery is reverted, WOM durably closes an unfinished parent apply so it
cannot resume afterward. Duplicate reconciliation can likewise revert one
authenticated interrupted journal from before or after receipt publication,
after revalidating the original approval.

If that duplicate revert reports `finalization_pending`, resume only the same
pending operation:

```powershell
archive duplicate-object-reconcile <archive-root> --revert --resume --reviewed-by <same-reviewer> --format json
```

WOM reauthenticates the existing claim and opens no second approval window. A
`started` claim resumes idempotently; a `succeeded` claim completes only the
finalizer. The resume path does not write the manifest again.

If the first revert stops in an unknown state, use its fixed safe action
`rerun_duplicate_revert_resume_with_same_reviewer`. The text output gives the
same instruction without exposing an approval id, private value, or path. A
failed explicit resume does not ask you to loop and retry it again.

The person chooses only the plain operation or cancel. WOM performs the counts,
hashes, drift checks, source binding, and independent verification. A client
archive changes only after the released project runtime runs that explicitly
chosen project-scoped operation; publication or installation is not recovery
evidence.

See the [v0.4.8 release note](wom-kit/docs/releases/v0.4.8.md).

## v0.4.7 Receipt-Bound Local Recovery

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.7/wom_kit-0.4.7-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.7` from a new process. Installing the wheel does
not modify an archive. `objet-capture --exact-local` and
`revert-edge --exact-local` use one native decision bound to the selected local
effect. The capture-link, locator, marker, and title recovery modes compute the
complete private manifest themselves; the person chooses only run or cancel.
Resume or revert uses the original private control and never asks the person to
recount archive records or compare digests.

See the [v0.4.7 release note](wom-kit/docs/releases/v0.4.7.md).

## v0.4.6 Exact R2 Preservation and Formal Adoption

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.6/wom_kit-0.4.6-py3-none-any.whl"
archive --version
```

Require exactly `archive 0.4.6` from a new process. A dry-run computes and
binds the evidence but does not read credential values, call the provider, or
write anything. For local-only byte protection, use the existing
`object-storage-adopt-existing` family with `--preserve-local-only`; for
verified key-map reconciliation, use `--formal-adoption`. Do not use the
legacy adopt approval path, which remains closed.

WOM verifies counts, hashes, drift, remote evidence, checkpoints, and receipts.
The person does not recount the archive or compare digests; the native window
asks only whether to run the plainly described exact operation or cancel.
Publishing or installing the release does not apply either operation to a
client archive.

See the [v0.4.6 release note](wom-kit/docs/releases/v0.4.6.md) and the
[object-storage execution contract](wom-kit/docs/object-storage-adapter-execution-contract.md).

## v0.4.3 Exact Recovery and Git Backup

Install only after the matching public Release lists the exact wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
archive --version
```

Close older WOM processes and require exactly `archive 0.4.3` from a new
process. This replaces the global CLI only. Inspect the project-local source
and PATH candidates separately; do not hand-edit a project pin.

v0.4.3 adds approval-gated writers to existing command families. The safe
order for a real archive is:

1. require a clean Git worktree and verify the current remote ref;
2. generate the content-free plan and exact manifest without approval;
3. review counts, reason codes, manifest digest, and intended target version;
4. approve only through the native exact-human dialog;
5. if interrupted, use the explicit same-claim resume path rather than
   starting a second approval;
6. independently verify the disk result and exercise the exact field-scoped
   revert contract on reviewed evidence; and
7. run the exact Git commit/non-force-push writer and verify its remote-ref
   receipt.

Letter 138 planning stays inside the existing migration family:

```powershell
archive migrate <archive-root> `
  --target notion-source-properties `
  --source-mirror <reviewed-preserved-mirror> `
  --acceptance <private-acceptance-output> `
  --dry-run `
  --progress `
  --format json
```

The plan must account for the complete source snapshot as `backfill`,
`already_equal`, `unmapped_no_canonical_target`, or `human_review`, with zero
unexplained populated-property omissions. `unmapped_no_canonical_target` is
preserved unresolved evidence, not a drop or a repaired page. Do not approve a
partial source scan, a changed mirror, or an acceptance document whose counts
or digests differ.

Git backup and project update reuse their existing top-level command families;
run `archive git-backup-plan --help` and
`archive project-version-update --help` from the verified v0.4.3 process for
the exact approval/resume options. Never put a credential in an argument,
environment variable, URL, or pasted transcript.

See the [v0.4.3 release note](wom-kit/docs/releases/v0.4.3.md),
[ExactOperationManifest v1](wom-kit/docs/exact-operation-manifest-v1.md),
[Git backup guide](wom-kit/docs/git-backup-plan.md), and
[project update guide](wom-kit/docs/project-version-update.md).

## v0.4.2 Read-Only Git Backup Planning

v0.4.2 is the read-only planning foundation for Letter 139. Do not run the URL
below merely because it appears in source documentation. It becomes an install
command only after the matching public GitHub Release exists and lists the
exact wheel.

Replace an older isolated `uv tool` installation with:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.2/wom_kit-0.4.2-py3-none-any.whl"
archive --version
```

Close older WOM processes first and require exactly `archive 0.4.2` from a new
process. This replaces only the global Python tool selected by `PATH`; it does
not update a project-local source mirror or pin, archive content, Agent Skill,
Git worktree, remote ref, or provider.

The new commands inspect only:

```powershell
archive git-backup-plan <archive-root> `
  --remote origin `
  --dry-run `
  --format json

archive git-backup-reconcile-plan <archive-root> `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --remote origin `
  --dry-run `
  --format json
```

Both keep `ready_for_write: false`, `writer_available: false`, and
`would_change: []`. They do not add, reset, checkout, commit, merge, rebase,
delete, fetch, pull, push, or change a remote ref. The initial remote observer
uses anonymous HTTPS only; authenticated/private HTTPS can be unavailable, and
SSH/scp-like or credential-bearing remotes fail closed. Do not put a token in
the URL to bypass the boundary.

`inspection_complete` is not backup completion. v0.4.2 does not choose files
or commit groups, create commits, push, perform a provider API re-query, or
publish completion evidence. See the [Git Backup Plan](wom-kit/docs/git-backup-plan.md)
and [v0.4.2 release note](wom-kit/docs/releases/v0.4.2.md).

## v0.4.1 Emergency Global-CLI Bootstrap And One Link Apply

v0.4.1 is a narrow recovery release. Do not run the URL below merely because
it appears in source documentation. It becomes an install command only after
the matching public GitHub Release exists and lists the exact wheel.

If v0.4.0 is already installed with `uv tool`, replace that isolated global
CLI environment with the exact released wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.1/wom_kit-0.4.1-py3-none-any.whl"
archive --version
```

`uv tool install` normally replaces an existing tool that `uv` manages. Do not
add `--force` unless `uv` explicitly reports an unmanaged executable collision;
that option permits replacing executables outside the existing managed tool.

Close any older WOM process first, then run `archive --version` in a new
process and require the exact output `archive 0.4.1`. The command updates only the global Python
tool selected by `PATH`. It does not update `.zettel-kasten/source`, a project
pin, an archive, the packaged Agent Skill installed in an AI host, or any
provider. `project-version-update`, collision mutation, and
`project-bytecode-repair` approval remain fixed closed in v0.4.1, so an
existing project-local v0.4.0 mirror stays unchanged. Do not hand-edit its pin
to pretend that the project mirror was upgraded.

### Reopened operation

Only the single structured `zettel-objet-link` apply route moved out of the
canonical fixed-close inventory. Preview one exact target first:

```powershell
archive zettel-objet-link <archive-root> `
  --zettel-id <zettel-id> `
  --object-id sha256:<64-lowercase-hex> `
  --role <reviewed-role> `
  --dry-run `
  --format json
```

Review the returned content-free plan. Then repeat the same target, object,
role, and optional label with the exact returned plan digest, a human reviewer,
and `--approve`:

```powershell
archive zettel-objet-link <archive-root> `
  --zettel-id <zettel-id> `
  --object-id sha256:<64-lowercase-hex> `
  --role <reviewed-role> `
  --expected-plan-sha256 <64-lowercase-hex> `
  --reviewed-by person:reviewer-id `
  --approve `
  --format json
```

If the preview used `--path` or `--label`, the approval must use the same
value. The local interactive Windows CLI shows the native exact-human dialog.
The binding covers one zettel, one already manifested Objet, role and optional
label, exact plan and target set, snapshot/receipt effects, and the stable
per-zettel control artifact. The writer rechecks those facts before mutation
and verifies durable readback. MCP remains plan/audit only.

A claim left in `started`, an uncertain effect, or an approval reconciliation
result is not a retry signal. Stop and inspect that exact claim. Do not create a
second approval automatically.

### Still closed

`zettel-objet-link-revert` remains preview-only. Every objet-capture approval,
including enablement, selection, single capture, and batch capture, also
remains fixed closed. v0.4.1 therefore has 78 current canonical fixed-closed
commands: it subtracts only `zettel-objet-link` from the v0.4.0 list. The
v0.4.0 section and its exact 79-command release inventory are historical and
remain unchanged. See the [v0.4.1 release note](wom-kit/docs/releases/v0.4.1.md).

## v0.4.0 Exact Human Control And Operator Friction

Install only after the exact v0.4.0 GitHub Release lists the verified wheel.
Start a new process, confirm `archive --version`, and discard every old dry-run
digest before reviewing a v0.4.0 write.

### What changed

Supported high-impact single operations now use a native Windows TaskDialog.
The dialog binds safe operation, plan, target set, warnings, checklist, archive
identity, and reviewer. Confirmation immediately creates one authenticated
durable `started` claim before the writer runs. The writer re-derives the
binding immediately before mutation, and the workflow alone finalizes the
claim. There is no issued approval token or expiry window.

Human-artifact root and lifecycle registration, byte-identical duplicate
reconciliation, approval-integrity overlays, source-fidelity session evidence,
AI draft creation, mint, promotion, one-edge writes, and draft retirement use
this boundary. Exact historical approval links require an authenticated
`succeeded` claim and upgrade the original effect only when `effect=created`.

For human artifacts, register an exact root with `root_kind=external_project`
to scan only `<root>/.wom-scratch`, or `root_kind=external_delivery` to scan the
reviewed root itself. `--project-root` and `--external-root` are aliases for the
selected root. WOM never auto-scans Downloads or a home directory, and only an
exact-human-approved registration contributes scan/closeout authority.

### What to do

Always preview first, review the content-free digests and warning codes, then
approve the unchanged plan from a local interactive Windows CLI. MCP remains
plan/audit only for these writes.

Do not approve unbound compound commands in v0.4.0. `mint-zet-batch`,
`retire-draft-batch`, `zettel-edge-batch`, `revert-edge`, `revert-batch`,
`zet-revision-write`, `zet-revision-restore-write`, `zettel-objet-link`,
`zettel-objet-link-revert`, and `notion-objet-link-convert` support preview but
not mutation. Activity-group membership add/removal and their recovery
executors, abstract-backfill write/revert/recovery, title-remap
write/revert/apply-recovery/revert-recovery, never-minted draft discard/restore,
and mint/retired-draft receipt reconciliation are likewise plan/audit or
preview-only. Relation-candidate acceptance is also closed. Every affected
approve attempt fails before private target read or mutation with
`compound_exact_human_approval_binding_required`.

The CLI now enforces one canonical fixed-close inventory of exactly 79 top-level
command names. Each affected `--approve` help entry says approval is unavailable in
v0.4.0 and points to the command-specific dry-run, plan, preview, or audit
surface. Use the exact list in the v0.4.0 release note; do not infer write
authority from an older command example or receipt. Nested derive capture,
non-exact/non-AI draft creation, real init, and parcel/pack creation are
separately fixed closed.

Letter 138 is an urgent follow-on, not part of v0.4.0. This release does not
detect or repair historical Notion typed-property loss. Its current Notion
recovery surfaces recover page bodies or locations only and are not a complete
source mirror. Do not treat a successful v0.4.0 recovery preview as property-
preservation evidence; wait for the separate read-only loss audit and
exact-approved backfill workflow.

The same v0.4.0 fixed blocker covers project update/collision mutation,
bytecode repair, saved-view write/revert, private objet metadata write,
identity reconciliation, legacy-coordination cleanup, archive migration,
markup normalization apply/revert/recovery, Principal register/unregister,
objet-capture enable/selection/single/batch, external import, source
registration, ownership transfer, object-storage mutation, Notion recovery,
external-locator mutation, source-intake recording/batches, quarantine
decisions, delegation, Tiro fetch/capture, Notion manifest labeling, GitHub
metadata setup, KeePassXC write, IMAP manifest/header execution, source scan,
onboarding, restore drill, standalone AI scratch cleanup, gitignore repair,
runtime-skill install/uninstall, and catalog-pass cleanup. Their read-only plans, previews, and audits remain
available where documented. Historical receipts and the older command examples
below are compatibility evidence only; they are not current v0.4.0 run
instructions and do not grant write authority.

A claim left in `started` means the outcome is unknown and requires
reconciliation. Never retry it automatically. See the
[v0.4.0 release note](wom-kit/docs/releases/v0.4.0.md) and
[Exact Human Approval Contract](wom-kit/docs/exact-human-approval-contract.md).

## v0.3.320 One-Use Credential Capability Broker

Install only after the exact v0.3.320 GitHub Release lists the verified wheel.
Repository files do not update an isolated older WOM-kit installation. Start a
new process and confirm `archive --version` before creating a new recovery plan.

### What changed

The existing `notion-page-recovery` approval now creates one fresh, expiring,
secret-free capability for that exact spawned worker invocation. It binds the
request and plan digests, reviewer, selected authenticated receipt/lifecycle
scopes, fixed read-only Notion endpoints, required registered capabilities,
one-use ceiling, and a bounded provider-attempt budget.

Inside the isolated worker, WOM validates those bindings and exclusively writes
an archive-key-HMAC claim before the first native credential read. Any existing
leaf permanently spends the capability id, including malformed or unfinished
state. Failure or crash requires a fresh approved invocation; the old id cannot
be replayed.

Before each provider attempt, WOM reauthenticates the claim and exact current
credential authority, then spends one allowed endpoint/scope budget unit. The
HMAC claim stores id/digest, request/plan, budgets, status, and count; the
durable recovery receipt stores only reference schema/id/digest; the parent
returns a separately validated secret-free use summary. A claim-finalization
failure cannot be reported as success.

### What to do

This subsection records the historical v0.3.320 contract. Under v0.4.0 create a
fresh bounded preview only; the recovery approval branch is fixed fail-closed
before credential read, provider call, or archive mutation with
`compound_exact_human_approval_binding_required`:

```powershell
archive notion-page-recovery-plan <archive-root> --request <archive-relative-reviewed-recovery-request.json> --max-items 5 --offset 0 --dry-run --format json
```

Do not retry automatically after an expired, replayed, changed, unknown, or
finalization-failed capability result. Review the content-free result and make a
new plan for diagnosis if a retry would otherwise be appropriate. A fully hash-verified local replay
creates no claim, reads no credential, and calls no provider.

An existing registered credential does not need to be entered again when its
authenticated receipt, lifecycle, native fingerprint, provider/workspace, and
reviewed scope remain valid. v0.3.320 adds no popup or password manager. Never
put a PAT in chat, argv, environment, ordinary stdin, or a file.

See the [v0.3.320 release note](wom-kit/docs/releases/v0.3.320.md),
[Credential Capability Contract](wom-kit/docs/credential-capability-contract.md),
and [decision log](wom-kit/docs/archive-infra-decision-log-2026-08-15-v03320-credential-capability-broker.md).

## v0.3.319 Native Credential Popup And Causal Evidence

Install only after the exact v0.3.319 GitHub Release lists the verified wheel.
Repository changes do not update an isolated older WOM-kit installation. Start
a new process, confirm `archive --version`, and discard every older
`credential-adopt` dry-run digest before planning enrollment again.

### What changed

The failed terminal-input prototypes are withdrawn. First enrollment and
explicit replacement now use one separate native Windows popup in an isolated
spawned child. The popup uses a standard single-line password EDIT for ordinary
editing and paste behavior, but an opaque sibling covers the whole field so no
value, mask glyph, caret, count, or length is visible. WOM never reads the
clipboard. Confirm is disabled while empty; Cancel, X, and Escape stop before a
completed secret.

The exact input intent is now part of the product boundary:

- production `credential-adopt` hard-codes
  `CredentialPopupInputIntent.live_registration` and shows the blue banner
  `실제 자격 증명 등록`;
- the source-tree acceptance helper hard-codes
  `CredentialPopupInputIntent.synthetic_acceptance`, shows the red banner
  `합성 입력 테스트 · 실제 키 입력 금지`, and warns never to enter or paste a
  real credential.

A missing intent or plain string fails before the popup can show or any store or
provider access can begin.

The child detaches before popup/native/store/provider/archive work and sends the
fixed `popup_child_detached` acknowledgement. The parent accepts only
acknowledgement → final mapping → terminal pipe EOF and joins every normally
started child. Its narrow `SIGINT`/`SIGBREAK` start lease is restored before
receiving. Raw input and exception text never cross IPC.

### Synthetic popup acceptance

The acceptance helper keeps its historical filename but now emits
`wom-kit/windows-credential-popup-acceptance/v0.1` and uses popup-only routes.
It requests no PAT and performs no registration, store write, or provider call.

Run only with the public fixed challenge:

```powershell
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family codex_desktop --launch-route codex_desktop_native_popup --gesture direct_keyboard_typing --format json
```

Do not enter an actual credential. A pass requires an exact challenge match,
the synthetic banner/warning, complete value-and-length opacity, correct Confirm
gating, normal popup closure, and legible Korean. Injected tests are not physical
human evidence.

The pre-intent human row remains failed: it received a complete non-empty
mismatch, and the person later clarified that the old harness copy had led them
to enter an actual secret. The child wiped it and no value reached receipt JSON,
IPC, a store, or a provider. That synthetic row remains failed. Do not repeat
the synthetic helper as a prerequisite for this recovery; it is optional future
acceptance evidence only.

### Actual registration

After the published v0.3.319 runtime is verified in a new process, the operator
may create one fresh registration dry-run. The synthetic helper is not a gate:

```powershell
archive credential-adopt <archive-root> --account-label <public-safe-account-label> --workspace-label <public-safe-workspace-label> --purpose notion-page-recovery --task-summary "<public-safe-task-summary>" --connection-reason "<public-safe-connection-reason>" --reviewed-anchor-page-id <reviewed-anchor-uuid> --interactive --dry-run --format json
```

Review the exact request digest, then repeat the same public-safe fields once
with `--expected-request-sha256 <fresh-request-sha256> --approve`. Enter an
actual PAT only when the popup top banner says `실제 자격 증명 등록`. Never put
it in chat, argv, an environment variable, ordinary stdin, a document, or the
synthetic helper. Do not retry automatically.

Actual credential registration is still `not_performed`; this guide does not
claim store persistence or provider acceptance.

### Causal failures

The v0.3 product envelopes still expose only:

```text
credential_input_received
complete_line_received
temporary_store_write_attempted
provider_request_attempted
```

Unknown child state projects four nulls.
`credential_input_invalid_for_provider` covers complete malformed, control,
provider-shape-invalid, over-limit, or locally oversized input before store and
provider work. `credential_input_boundary_failed` preserves truthful `1000`
or `1100` evidence with operator action
`repair_secure_input_boundary_and_create_a_new_plan`, rollback not required,
store false, and provider false. `provider_auth_rejected` requires an actual
provider request. `provider_request_not_attempted` covers a temporary store
write whose verifier never crossed the provider boundary. Rollback `deleted`
requires an exact post-delete absence probe.

### Upgrade truth

A source checkout, fake Win32 tests, DPI-correct render, or passing injected
acceptance row does not prove merge, external CI, exact tag, GitHub Release,
wheel publication, fresh installation, physical synthetic acceptance, actual
registration, provider acceptance, durable persistence, or recovery.

## v0.3.318 Credential Paste And Failure Stages

Install only after the exact v0.3.318 GitHub Release lists the verified wheel.
Repository changes do not update an isolated older WOM-kit installation. Start
a new process and confirm `archive --version` before making a new adoption
plan. Discard any older dry-run digest because the running version and reviewed
request must agree.

The separate black Windows console explains the supported paste actions
directly above the masked input: `Ctrl+V`, `Shift+Insert`, Windows Terminal's
default `Ctrl+Shift+V`, and host-dependent right-click. Characters and length
remain hidden, `Ctrl+C` is ignored during the prompt, and empty Enter is the
documented cancellation gesture.

After a complete non-empty line reaches WOM, v0.3.318 displays
`입력값을 받았습니다. 검증 중입니다.` briefly. That confirms receipt at the
console boundary, not provider acceptance or durable storage. WOM never reads
the clipboard programmatically.

The v0.3.318 parent result is `wom-credential-workflow-result/v0.2`; the child
is `wom-credential-secure-intake-result/v0.2`. Its five fixed outcomes are
`credential_input_cancelled_or_empty`, `credential_input_not_received`,
`provider_auth_rejected`, `provider_identity_endpoint_unavailable`, and
`reviewed_anchor_inaccessible`, with pre-store and rollback relationships.

The source tests and synthetic Win32 canaries did not prove a physical paste
gesture under every terminal host. See the
[v0.3.318 release note](wom-kit/docs/releases/v0.3.318.md),
[Letter 131 guide](wom-kit/docs/letter131-credential-console-paste-and-failure-stages.md),
and [Letter 131 decision](wom-kit/docs/archive-infra-decision-log-2026-08-13-v03318-letter131-credential-input.md).

## v0.3.317 Credential Console And Staged-Cleanup Safety

Install only after the exact v0.3.317 GitHub Release lists the verified wheel.
Repository changes do not update an older isolated WOM-kit installation. Open a
new process and confirm `archive --version` before using the corrected paths.

There is no automatic canonical-zet rewrite, object-store rewrite, provider
write, credential replacement, or credential-store deletion in this release.

### First credential enrollment or reviewed replacement

Discard any older credential-adoption dry-run digest. v0.3.317 binds the helper
AI's reviewed public-safe task summary, connection reason, and replacement
intent into a new request digest.

```powershell
archive credential-adopt <archive-root> --account-label <safe-label> --workspace-label <safe-label> --task-summary "<public-safe current task>" --connection-reason "<public-safe reason>" --reviewed-anchor-page-id <uuid> --interactive --dry-run --format json
archive credential-adopt <archive-root> --account-label <same-safe-label> --workspace-label <same-safe-label> --task-summary "<same public-safe current task>" --connection-reason "<same public-safe reason>" --reviewed-anchor-page-id <same-uuid> --interactive --expected-request-sha256 <request-sha256> --approve --format json
```

The approved command opens one separate visible Unicode Windows console with
input echo disabled. Enter the PAT only there. WOM's fixed notice explains that
the credential is not sent to the helper AI or chat. Empty Enter or Ctrl+C
cancels. After a successful authenticated registration, ordinary later work
reuses the saved Windows credential and must not call `credential-adopt` again.

Use `--replace-existing` in both commands only for a separately reviewed
rotation or repair. Without that flag, a matching authenticated registration is
kept and no new input console opens only after WOM authenticates its receipt,
reads the exact saved Windows entry inside the worker, verifies its secret
fingerprint, and rechecks the current reviewed Notion anchor. A missing,
unreadable, or fingerprint-mismatched saved entry stops and requires a fresh,
separately reviewed replacement plan. If the current anchor/provider check
fails, keep the saved credential and review the page, sharing, and connection
before retrying without another prompt. Account/workspace labels are display
text, so changing only those labels must not open another prompt.

Notion exposes two different identity shapes. An internal integration returns
`bot.workspace_id`, which WOM uses as its provider workspace basis. A person
PAT does not return a workspace ID. For a PAT, WOM instead derives the
`notion_pat_token_scope_v1` witness from the archive-keyed fingerprint of the
exact saved token and rechecks both the current person identity and reviewed
page access. This allows the same saved PAT to be reused for another page
without another prompt. A different PAT remains a different scope, even if it
belongs to the same Notion workspace; rotation or reconciliation requires a
separate reviewed lifecycle operation.

### Existing v0.3.311-v0.3.316 registrations

Those versions wrote authenticated v0.1 receipts whose workspace fingerprint
was derived from the reviewed page. v0.3.317 never rewrites that receipt or
stores the PAT again. For exactly one compatible registration, WOM
authenticates the old receipt, verifies the exact saved-secret fingerprint,
performs the current provider/page check, and appends one authenticated local
workspace-scope evolution. A compatible one-credential lifecycle is moved to
that new authority without another prompt, Credential Manager write, or
deletion. With no lifecycle, the evolved registration still needs a human
default selection. Duplicate or complex lifecycle state stops for review
before first publication. If the process stops after the evolution but before
the lifecycle transition, the old broker binding remains blocked and rerunning
the same approved operation completes the idempotent transition.

### Before removing a staged folder

Run a fresh report-only verification:

```powershell
archive staged-cleanup-check <archive-root> --staged <archive-relative-staged-folder> --dry-run --format json --output .wom-scratch/diagnostics/staged-cleanup-v03317.json
```

Only exit `0` and `safe_to_cleanup: true` authorize the human to consider a
separate manual cleanup. Ordinary objets need matching store bytes, manifest,
and capture receipt. Exact BOM-free paired text needs its complete direct
derived-text evidence chain. A deferred entry stays staged and forces exit `1`.
The command itself never deletes or moves data. Do not edit a manifest or
receipt by hand to force a safe result.

See the [v0.3.317 release note](wom-kit/docs/releases/v0.3.317.md),
[Letters 118 and 119 guide](wom-kit/docs/letter118-119-credential-continuity-and-notion-page-recovery.md),
[staged-cleanup evidence decision](wom-kit/docs/archive-infra-decision-log-2026-08-13-v03317-letter130-staged-cleanup-evidence.md),
and [operation-control guide](wom-kit/docs/operation-control.md).

## v0.3.316 Python Cache Collision Recovery

v0.3.315 could correctly detect a complete batch of ignored Python cache
collisions but offered only slow one-entry inspection and no usable recovery
for that kind. v0.3.316 adds one complete inspection and a narrowly bounded
official cache-repair route.

Install the exact v0.3.316 wheel only after the matching GitHub Release lists
it. Start a new process and confirm `archive --version` before working on the
project. Pause editors, sync/backup clients, and other Git writers for repair
and update approval.

Keep the target and `materialization_plan_sha256` from a fresh blocked
`project-version-update --dry-run`. Inspect the complete collision set once;
do not pass individual `entry_ref` values:

```powershell
archive project-version-update-collision <project-or-archive-root> --target v0.3.316 --expected-plan-sha256 sha256:<materialization-digest> --action inspect-all --dry-run --format json
```

Continue only if the result reports the exact complete set as eligible for
`project_bytecode_repair`. Preview a separate repair bound to the same target
and digest:

```powershell
archive project-bytecode-repair-plan <project-or-archive-root> --target v0.3.316 --expected-materialization-plan-sha256 sha256:<materialization-digest> --dry-run --format json
```

Review its exact counts and `plan_sha256`, then approve that repair plan:

```powershell
archive project-bytecode-repair <project-or-archive-root> --target v0.3.316 --expected-materialization-plan-sha256 sha256:<materialization-digest> --expected-plan-sha256 <repair-plan-sha256> --approve --reviewed-by <actor> --affirm-external-writers-quiescent --format json
```

The repair accepts only the exact supported ignored Python bytecode/cache set.
It does not delete user-authored source, fetch a target, change `HEAD` or the
project version pin, retry the updater, or approve an update. If inspection or
repair reports unavailable, blocked, partial, uncertain, or retained-evidence
state, stop and follow its fixed next action.

After repair, discard the old updater approval context. Run a fresh
`project-version-update --dry-run`, review the new plan, and approve that update
separately. Finally start a new process and require `archive version` to show
running import, project source, pin, and exact tag agreement.

See the [v0.3.316 release note](wom-kit/docs/releases/v0.3.316.md),
[project update guide](wom-kit/docs/project-version-update.md), and
[bounded operation-control guide](wom-kit/docs/operation-control.md).

## v0.3.315 Update-Collision And Paired-Batch Recovery

Install the exact v0.3.315 artifact only after the matching Release lists the
verified wheel. Start a new terminal process and confirm `archive --version`
before touching a real project or archive.

### If a project update reports a collision

Do not guess the hidden path, delete or move a file by hand, repeat approval,
or launch another updater. Keep editors, sync/backup clients, and Git writers
paused. Retain the returned `entry_ref` and `materialization_plan_sha256`, then
inspect that exact item:

```powershell
archive project-version-update-collision <project-or-archive-root> --target v0.3.315 --entry-ref update-entry:0001 --expected-plan-sha256 sha256:<digest> --action inspect --dry-run --format json
```

If inspection says the regular entry is eligible, preview preservation:

```powershell
archive project-version-update-collision <project-or-archive-root> --target v0.3.315 --entry-ref update-entry:0001 --expected-plan-sha256 sha256:<digest> --action preserve-relocate --dry-run --format json
```

Review the fresh preservation plan, then approve that same plan with
`--reviewed-by <actor> --affirm-external-writers-quiescent --approve`. This
moves the current private bytes to a WOM-owned preservation location. It does
not delete or overwrite them, fetch the target, or retry the updater. After it
finishes, run `project-version-update --dry-run` again and approve that new
updater plan separately. The receipts provide
`unauthenticated_private_state_internal_consistency`; they are not a MAC,
signature, ACL, or general defense against a coordinated same-user rewrite.

```powershell
archive project-version-update-collision <project-or-archive-root> --target v0.3.315 --entry-ref update-entry:0001 --expected-plan-sha256 sha256:<digest> --action preserve-relocate --approve --reviewed-by <actor> --affirm-external-writers-quiescent --format json
```

### If a v0.3.314 paired capture stopped halfway

Do not copy already captured originals again. Re-run the unchanged
`objet-capture-batch` request first:

```powershell
archive objet-capture-batch <archive-root> --manifest <same-archive-relative-json> --dry-run --format json
archive objet-capture-batch <archive-root> --manifest <same-archive-relative-json> --expected-plan-sha256 <fresh-plan-sha256> --approve --reviewed-by <actor> --format json
```

The v0.3.315 result separates original and derived requested, written, skipped,
and blocked counts. Exact existing originals are skipped while missing paired
derived text is completed. If the original staging files are no longer
available, use the durable original capture receipts to build a reviewed
derived-text manifest with their source object IDs, then use
`derive-text capture --from-manifest`; do not recopy originals just to obtain
those IDs. Treat `evidence_incomplete`, `recovery_required`, and
`batch_capture_outcome_unverified` as stop-and-review states, not success.

See the [v0.3.315 release note](wom-kit/docs/releases/v0.3.315.md),
[project update guide](wom-kit/docs/project-version-update.md), and
[derived-text guide](wom-kit/docs/derived-text.md).

## v0.3.314 Letter 126 Long-Operation And Generated-Index Recovery

v0.3.314 does not rewrite canonical zets, objets, manifests, durable private
metadata authority, or database schemas during installation. It changes the
disposable generated-index storage contract: an older WAL-mode index must be
rebuilt once before protected index-backed work continues.

After installing the exact release and starting a new process, stop other
archive/SQLite writers and use fresh private diagnostic filenames:

```powershell
archive index <archive-root> --progress --output .wom-scratch/diagnostics/index-v03314.json --format json
archive index-health <archive-root> --dry-run --progress --output .wom-scratch/diagnostics/index-health-v03314.json --format json
```

The first command converts only the disposable generated cache to rollback
`DELETE` mode and rebuilds the private projection in the same transaction. The
second must report a clean current result before protected search/view/mint
work resumes. Do not hand-edit, rename, or delete SQLite files or sidecars.

For future long project updates or index operations, always opt into a new
`--output` file and retain the opaque `operation_ref` printed at startup. If
the caller times out, do not start a duplicate writer. Inspect the same run:

```powershell
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action status --dry-run --format json
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action wait --timeout-seconds 60 --dry-run --format json
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action recovery-plan --dry-run --format json
```

A wait deadline is not failure or cancellation. Cancel and resume are not
implemented; cancel returns nonzero `operation_cancel_not_supported` and writes
nothing. There is no daemon, queue, background launcher, force kill, lock
deletion, or MCP control. See [Bounded operation control](wom-kit/docs/operation-control.md),
[v0.3.314 release notes](wom-kit/docs/releases/v0.3.314.md), and the
[decision record](wom-kit/docs/archive-infra-decision-log-2026-08-11-v03314-letter126.md).

## v0.3.313 Source Fidelity And Private Verbatim Preservation

v0.3.313 does not rewrite existing zets, drafts, receipts, or source objets.
Human-written draft creation remains compatible. It intentionally changes every
new `ai_assisted` and `ai_generated` draft workflow: the first write now requires
an explicit source-fidelity contract and an attributed human-approved replay.
An AI identity in `created_by` or `assisted_by`, or any non-empty
`local_ai_sessions` evidence, cannot be relabeled as `human_written`; that
fails with `ai_provenance_requires_ai_creation_mode`.

For a new AI draft, first preserve the source as a manifested local
content-addressed objet. Preview with all of these inputs:

```powershell
archive create-draft <archive-root> --title <title> --body-file <private-candidate> --abstract <abstract> --facet <key=value> --creation-mode ai_assisted --created-by ai_runtime:<runtime> --assisted-by ai_runtime:<runtime> --source-fidelity <verbatim|faithful_summary|sanitized_derivative> --fidelity-audience <audience> --fidelity-source-object-id <sha256:...> --dry-run --format json
```

Review the proposed body and content-free plan, then replay the unchanged
request with `--approve --draft-approved-by <human-actor>
--expected-body-sha256 <sha256>
--expected-source-fidelity-plan-sha256 <sha256>`. The approved operation creates
one inbox draft and one private create-only fidelity receipt. It does not mint,
share, export, or call a provider.

Before mint, run `mint-zet --dry-run` again. Approval must include the returned
current `--expected-source-fidelity-plan-sha256` together with the existing
`--reviewed-by` and `--approve` gates. WOM re-reads the manifested source and
raw draft body; source drift or a changed verbatim region blocks publication.

Existing AI drafts are not assigned a guessed mode. When a human has reviewed
one such draft against its source, record the compatibility affirmation as
`--affirm legacy_source_fidelity_reviewed --reviewed-by <human-actor>` during
the mint workflow. This is attributed review evidence, not retrospective proof
that old bytes were verbatim.

`verbatim` is limited to a personal archive and `private_self`. It preserves
private personal data but never credential secrets. `audience` records intent;
it is not an ACL or permission to disclose anything. For other recipients,
keep the private source unchanged and make a separately reviewed
`sanitized_derivative`.

See the [source-fidelity guide](wom-kit/docs/source-fidelity-and-private-verbatim.md),
[v0.3.313 release note](wom-kit/docs/releases/v0.3.313.md), and
[decision record](wom-kit/docs/archive-infra-decision-log-2026-08-10-v03313-source-fidelity.md).

## v0.3.312 Letters 120 And 123 Index Authority And Feedback Bodies

v0.3.312 intentionally requires one explicit rebuild of generated zettel
indexes created by older versions. It does not rewrite canonical zets or
automatically scan a real archive during installation.

Before using protected `search`, `view-zets`, or `mint-zet` behavior, run:

```powershell
archive index <archive-root> --progress --format json
archive index-health <archive-root> --dry-run --progress --format json
```

If a protected command returns `archive_index_rebuild_required`, do not trust
stale rows and do not replace the blocker with raw SQLite or a whole-archive
body scan. Rebuild explicitly, verify health, and retry the original request.

For a large mint preview, use `mint-zet --dry-run --progress`. Progress stays on
stderr and the one final result stays on stdout. A heartbeat is not approval or
completion evidence; canonical plus receipt evidence is still required after
the separate reviewed mint.

Substantive tool feedback is now composed from an ignored-local six-section
request through `operator-feedback-compose --dry-run` and its exact reviewed
replay. Check the body and metadata binding with
`operator-feedback-body-check --dry-run`, then use its
`feedback-body-sha256:<digest>` value in the existing feedback lifecycle
record. These commands do not submit feedback or prove delivery.

See the [Letters 120 and 123 guide](wom-kit/docs/letter120-123-index-lifecycle-and-feedback-body.md),
the [v0.3.312 release note](wom-kit/docs/releases/v0.3.312.md), and the
[decision log](wom-kit/docs/archive-infra-decision-log-2026-08-10-v03312-index-authority-and-feedback-body.md).

## v0.3.311 Letters 118 And 119 Credential Continuity And Reviewed Recovery

v0.3.311 is compatible with v0.3.310 archives and performs no automatic
credential migration, provider call, or canonical-zettel rewrite. Existing
credential-reference rows remain metadata only with store presence unchecked.

On Windows, use `credential-adopt` in dry-run mode first and approve only the
exact returned request digest. Approval opens a native masked dialog in a
spawned child. Never paste a PAT into a command argument, environment variable,
normal stdin, file, or chat. WOM and the helper AI never read the clipboard
directly; a deliberate human paste into the separate masked console is handled
only as console input. After authenticated listing, v0.4.0 supports only the
separate `credential-lifecycle --dry-run` plan. Its legacy reviewer-label
approval path is fixed closed before archive-key or credential access until an
exact-human binding exists. WOM does not delete or revoke the other valid
entries.

The reviewed Notion recovery request must stay under the ignored local profile
and contain the complete Letter 118 set: `zet_notion_db3` with 577 items and
`zet_notion_db1` with 43 items. Run `notion-page-recovery-plan --dry-run` for a
small `--max-items` slice and review the fixed capabilities and exact plan
digest. The v0.4.0 `notion-page-recovery` approval path is fixed closed before
credential reads, provider calls, or archive writes. Historical v0.3 recovery
receipts remain auditable, but do not authorize a new run.

This release does not mean a real PAT has been adopted or that all 620 pages
have been recovered. Those remain operator execution and human acceptance
steps. See the [Letters 118 and 119 guide](wom-kit/docs/letter118-119-credential-continuity-and-notion-page-recovery.md),
the [v0.3.311 release note](wom-kit/docs/releases/v0.3.311.md), and the
[decision log](wom-kit/docs/archive-infra-decision-log-2026-08-10-v03311-letter118-119-credential-lifecycle.md).

## v0.3.310 Letter 117 Reviewed Imported-Reference Completion

v0.3.310 is compatible with v0.3.309 archives and requires no automatic
archive migration or manifest-schema upgrade. It extends the existing reviewed
binding-manifest v0.2 and the same plan/apply/recovery/revert lifecycle.

Three exact imported placeholder shapes can now use reviewed static authority:
`<unknown:synced_block/>`, `<unknown:transclusion_reference/>`, and
`<unknown:transclusion_container/>`. Each occurrence must keep the exact
lowercase, attribute-free, self-closing spelling and may bind only to a
canonical same-archive `zettel_reference` or a fully manifested `objet`.
Repeated same-digest placeholders still require complete 1-based
`occurrence_index` coverage. Attributes, alternate case or spacing, paired
forms, incomplete selectors, `zettel_edge`, and `external_locator` authority
remain unchanged and block. The result is a static navigation or objet link;
it does not fetch a provider, reconstruct transcluded children, infer an edge,
or claim live synchronization.

An empty paired `database` fragment may bind to a reviewed
`zettel_reference` when its opening tag contains exactly required `inline` and
`url` attributes plus optional `data-source-url`; `inline` must be `true` or
`false`. The digest covers the full opening-and-closing fragment. A
self-closing database, visible inner content, missing or extra attributes,
invalid `inline`, or an objet/edge/locator binding remains byte-identical and
blocked. WOM creates only a static zettel link and does not materialize a
database view.

Protected Markdown and raw-HTML literals are terminal preserved content, not
automatically repairable migration debt. v0.3.310 closes fail-open gaps for
normalizable-looking tags inside quoted HTML attributes, unreviewed raw-HTML
blocks, multiline-label link reference definitions, and reference-definition
titles on the following line. If a protected context or any other blocker is
present, the complete proposed zettel body is discarded and its original
bytes remain unchanged. Normalizing only safe source spans outside a protected
literal remains future work.

Callout icon/color/indentation semantics, unknown column boundaries, and
`unknown:unsupported` content still cannot be removed losslessly and remain
fail closed. Continue to preview with
`markup-normalization-plan --only-ready --dry-run`, review the content-free
selectors and exact plan digest, and approve only the unchanged plan. Upgrade
itself performs no provider lookup or private-archive write.

See the [Letter 117 operator guide](wom-kit/docs/letter117-completion.md),
the [v0.3.310 release note](wom-kit/docs/releases/v0.3.310.md), and the
[decision log](wom-kit/docs/archive-infra-decision-log-2026-08-09-v03310-letter117-completion.md).

## v0.3.309 Letter 116 Occurrence And Reviewed Navigation Completion

v0.3.309 is compatible with v0.3.308 archives and requires no automatic
archive migration. Existing v0.1 markup-binding manifests remain readable for
a reference digest that occurs exactly once. Repeated byte-identical tags now
require a v0.2 reviewed manifest with a complete, one-based
`occurrence_index` set from `1` through the exact occurrence count. Missing,
mixed, duplicate, out-of-range, or stale selectors leave the source bytes
unchanged and block.

A v0.2 manifest may bind a self-closing `mention-page` occurrence to one
reviewed `zettel_reference`. This is a navigation link, not a semantic graph
edge: WOM creates or changes no `edges[]` row and infers no relationship. The
reviewed source id and path must remain unambiguous. The target must be
distinct from the source and resolve to exactly one regular, schema-valid,
canonical zettel in the same archive, and it must remain canonical when the
approved plan is reapplied under the writer lock. Ambiguous identity,
lifecycle drift, an invalid target, or a binding kind that does not match the
reference tag blocks without a write.

The normalizer may also remove one exact, attribute-free, self-closing
`<unknown:table_of_contents/>` placeholder when it occurs exactly once and is
the immutable original body's first non-empty line. It does not generate a
table of contents or other navigation text. Indented, attributed, repeated,
non-first-line, protected-context, or co-blocked forms remain byte-identical.
Bare `callout` and `database` tags plus the unsupported `unknown:` synced,
transclusion, column, and link-preview placeholder shapes remain fail closed
until their visible content or identity can be recovered without guessing.
Existing supported synced and column wrapper normalization is unchanged.

Continue to run `markup-normalization-plan --only-ready --dry-run`, review its
content-free selector and plan digests, and approve only the unchanged plan.
Apply, recovery, and revert keep the existing exact-snapshot, journal,
receipt, and byte-preservation contracts. No command scans a provider or
automatically edits a private archive during upgrade.

See the [Letter 116 operator guide](wom-kit/docs/letter116-completion.md),
the [v0.3.309 release note](wom-kit/docs/releases/v0.3.309.md), and the
[decision log](wom-kit/docs/archive-infra-decision-log-2026-08-09-v03309-letter116-completion.md).

## v0.3.308 Letter 115 Reference, Locator, And Table Completion

v0.3.308 is compatible with v0.3.307 archives and requires no automatic
archive migration. Existing locator records and historical receipts remain
readable. A locator record moves to the new schema only when an operator
approves a locator write.

Migration-markup normalization now treats one complete paired
`<file ...></file>` fragment as one reviewed binding candidate. Self-closing
`mention-page` can bind only through an existing reviewed `zettel_edge`, and
one self-closing `unknown:audio` can bind only to a verified manifested objet.
Nonempty or malformed file pairs, labeled page mentions, duplicate binding
rows, and repeated identity-free unknown-audio placeholders remain unchanged
and block rather than losing visible content or guessing identity.

Imported tables gain a strict lossless cell subset: self-closing Notion dates
become visible text, reviewed span wrappers are removed while preserving their
inline content, and literal pipes remain GFM-escaped. Scripts, inputs, block
markup, unsafe attributes or URLs, references, comments, and unbalanced markup
remain byte-identical and block. Fenced/inline code, declarations, raw code
elements, Markdown link targets/titles, and non-standalone or malformed tables
are protected rather than interpreted as migration markup.

For an older record with two reviewed duplicate active locators, first inspect
the content-free recovery projection, then name both the weaker target and the
active compatible row to keep:

```powershell
archive external-locator-deactivate-plan <archive-root> `
  --zettel-id <zet-id> --locator-id <target-locator-id> `
  --keep-locator-id <retained-locator-id> --dry-run --format json

archive external-locator-deactivate <archive-root> `
  --zettel-id <zet-id> --locator-id <target-locator-id> `
  --keep-locator-id <retained-locator-id> `
  --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

The apply command changes only the selected target status to `inactive`, keeps
row order and locator values, snapshots the exact prior record, and emits a
receipt accepted by the existing exact-byte locator revert. It refuses a
target referenced from canonical body content, a different occurrence anchor,
dropped reviewed coordinates, ambiguity, stale bytes, or a changed plan.
Inactive locators cannot satisfy new markup bindings.
Revert accepts only validated regular locator receipts, derives canonical
record/snapshot paths, rejects corrupt content-addressed snapshots, and rolls
the record back when a handled publication failure occurs.

See the [Letter 115 operator guide](wom-kit/docs/letter115-completion.md),
the [v0.3.308 release note](wom-kit/docs/releases/v0.3.308.md), and the
[decision log](wom-kit/docs/archive-infra-decision-log-2026-08-09-v03308-letter115-completion.md).

## v0.3.307 Exact-Root Legacy Coordination Cleanup

v0.3.307 is compatible with v0.3.306 archives and requires no archive
migration. It adds one explicit CLI command for an owner who already knows the
absolute root of a workspace containing retired `.mow-harness/` state. It does
not restore the retired external integration, search for installations, or run
from Doctor, archive discovery, restore, installation, project update, or
upgrade.

Preview one exact workspace without writing:

```powershell
$workspaceRoot = 'C:\path\to\one-workspace'
archive legacy-coordination-cleanup $workspaceRoot --dry-run --format json
```

Review only aggregate counts, blockers, and `plan_sha256`. Output contains no
filename, content, or local absolute path. This content-free dry-run is available
on every supported platform. `collab/` is never traversed or changed. Unknown or
case-drifted targets, unsafe Git environment, content found in any ancestor Git
index, a nested `.git` entry (blocked without traversal), links, junctions,
Windows reparse points or named streams, Linux `mnt_id`/other cross-mount
evidence, special or unreadable entries, an existing lock or old cleanup
tombstone, limit exhaustion, and scan drift all block. Inspect the local tree
itself before approval; privacy-safe aggregate output is not a substitute for
deciding that every byte is disposable.

Approved mutation is Windows-only in v0.3.307. A POSIX preview reports
`approval_platform_supported: false` and `safe_to_cleanup: false`; POSIX
`--approve` stops before lock acquisition and before mutation. Standard POSIX
does not provide a portable atomic operation that deletes a name only if it
still refers to the exact inode reviewed earlier, so WOM does not pretend that a
retained file descriptor solves that race.

On Windows, after the workspace owner authorizes irreversible cleanup, pause
every editor, sync/backup client, indexer, terminal, and other writer. Approve
only the exact unchanged plan:

```powershell
$planSha256 = '<64-lowercase-hex-from-plan-sha256>'
archive legacy-coordination-cleanup $workspaceRoot --approve --reviewed-by 'person:workspace-owner' --expected-plan-sha256 $planSha256 --affirm-workspace-owner-authorized --affirm-external-writers-quiescent --affirm-retired-state-disposable --format json
```

If `summary.backups_or_receipts_present` is `true`, also pass
`--affirm-backups-and-receipts-disposable`. If custom `--max-files` or
`--max-bytes` values were used during preview, repeat the same values during
approval.

During Windows approval, WOM retains handles to every workspace ancestor and
the workspace root for the complete operation, and uses retained verified
handles to dispose exact approved files and empty directories. It creates no
backup, cleanup receipt, or new tombstone rename. An old tombstone still blocks.
After the first mutation, any partial or uncertain result is
`partial_cleanup_pending`, not success; WOM does not automatically retry,
resume, or roll back. Removing filesystem entries is not secure media erasure
and does not remove storage remnants or other backup/sync copies.

See
[`wom-kit/docs/legacy-coordination-cleanup.md`](wom-kit/docs/legacy-coordination-cleanup.md),
[`wom-kit/docs/releases/v0.3.307.md`](wom-kit/docs/releases/v0.3.307.md), and
[`wom-kit/docs/archive-infra-decision-log-2026-08-08-v03307-legacy-coordination-cleanup.md`](wom-kit/docs/archive-infra-decision-log-2026-08-08-v03307-legacy-coordination-cleanup.md).

## v0.3.306 Retired Integration Cleanup

v0.3.306 is compatible with v0.3.305 archives and requires no archive
migration. WOM never bundled or invoked MOW Harness, and this release removes
the former external recommendation, unavailable repository link, dedicated
compatibility guide, and install/update/activation advice.

The repository-only artifact hygiene checker now offers the generic source
alias `LOCAL_ONLY_COORDINATION_STATE`, while preserving the exact historical
`LOCAL_ONLY_COLLAB_HARNESS` machine-output and import compatibility label.
Existing parsers and imports do not need to change. No WOM CLI command, MCP
tool, schema, zet, objet, receipt, manifest, index, or provider contract
changes.

Do not remove `collab/` or `.mow-harness/` merely because their names exist.
They can hold user-authored plans, prompts, mailboxes, installer metadata, or
secrets. Default archive-root Doctor checks, archive-root source discovery,
restore drills, and repository artifact-hygiene scans exclude both roots; the
artifact checker also refuses either root as its direct target. This quarantine
does not make an explicit human-selected path safe: do not point a separate
file-capture or staged-folder command at either root.
After backing up and reviewing an exact non-archive installation path, an
operator may remove obsolete external-tool bytes separately; WOM grants no
automatic cleanup authority and never changes a personal archive for this
retirement.

See
[`wom-kit/docs/releases/v0.3.306.md`](wom-kit/docs/releases/v0.3.306.md) and
[`wom-kit/docs/archive-infra-decision-log-2026-08-08-v03306-mow-harness-sunset.md`](wom-kit/docs/archive-infra-decision-log-2026-08-08-v03306-mow-harness-sunset.md).

## v0.3.305 Real-use Completion And Publication Visibility

v0.3.305 is compatible with v0.3.304 archives and requires no automatic
migration. It completes the remaining Letter 113 migration, locator, and title
workflows and closes the Letter 114 silent-publication gap.

After upgrading, start a session with:

```powershell
archive ai-start-here <archive-root> --dry-run --format json
```

Review `inbox_attention` before broad work. It reports unpublished counts and
publication-readiness signals without returning draft identities or bodies.
For more detail, run `inbox-pipeline-audit --dry-run`; the result authorizes no
automatic repair, discard, or mint.

AI-assisted/generated `create-draft` calls now require an explicit safe
abstract and at least one non-empty facet. A same-normalized-title inbox draft
blocks a second AI file so the existing draft can be revised in place. A human
rough-draft flow remains available and receives a warning. When a human asks to
publish, enter `mint-zet --dry-run` in the same task, report blockers or a
remaining approval gate immediately, and claim completion only after the
approved mint has canonical and receipt evidence.

For markup with unrelated blocked zets, use matching `--only-ready` plan and
write commands. Strict mode remains the default. See
[`wom-kit/docs/letter113-completion.md`](wom-kit/docs/letter113-completion.md),
[`wom-kit/docs/letter114-completion.md`](wom-kit/docs/letter114-completion.md),
and [`wom-kit/docs/releases/v0.3.305.md`](wom-kit/docs/releases/v0.3.305.md).

## v0.3.304 Project Update Forward-Only Fix

v0.3.304 is compatible with v0.3.303 archives and requires no migration. It
fixes a project updater comparison defect reported in beta Letter 112.

Run the normal no-write preview:

```powershell
archive project-version-update <project-or-archive-root> --target v0.3.304 --dry-run --format json
```

`forward_only.comparison_basis` is now
`recognized_project_pins_and_project_source_versions`, and
`runtime.used_for_forward_only_decision` is false. A newer runtime loaded
outside the project mirror may produce an informational warning, but does not
block an update that is forward relative to the project itself. A target below
any recognized project pin or source version still blocks.

Windows approval retains every existing exact-tag, origin, clean-tree,
external-writer-quiescence, receipt, rollback, and restart gate. See
[`wom-kit/docs/project-version-update.md`](wom-kit/docs/project-version-update.md)
and [`wom-kit/docs/releases/v0.3.304.md`](wom-kit/docs/releases/v0.3.304.md).

## v0.3.303 Artifact Lifecycle Inventory

v0.3.303 is compatible with v0.3.302 archives and requires no migration. It
adds a read-only checkpoint; existing files are not reclassified on disk and
nothing is cleaned automatically.

Run:

```powershell
archive artifact-lifecycle-inventory <archive-root> --dry-run --format json
```

Review `coverage.complete` before relying on counts. A limit, unreadable entry,
link/reparse point, concurrent change, malformed object manifest, invalid local
object layout, or invalid workpack control file blocks the relevant claim.
Default rows hide child paths. `--show-relative-paths` is only for attended
local review.

An `unmanifested_local_object_candidate` is not a proven orphan and is never
deletion approval. An expired workpack also remains a retention-review item.
The command reads no ordinary artifact body or object byte, writes nothing,
and checks no provider or sibling object store.

See
[`wom-kit/docs/artifact-lifecycle-inventory.md`](wom-kit/docs/artifact-lifecycle-inventory.md)
and
[`wom-kit/docs/releases/v0.3.303.md`](wom-kit/docs/releases/v0.3.303.md).

## v0.3.302 Saved-View Lifecycle

v0.3.302 is compatible with valid v0.3.301 archives and requires no automatic
migration. Saved-view discovery now fails closed: malformed YAML/UTF-8,
unsafe or oversized entries, unsupported filters, invalid ids, and duplicate
ids are reported rather than skipped.

Run `archive view-health <archive-root> --dry-run --format json` after upgrade.
If authority is valid, a new persistent navigation view can be created only
through a private `saved-view-write-request/v0.1`, dry-run, exact plan digest,
human reviewer, and `--affirm-view-reviewed`. Do not let an AI edit
`views/*.yml` directly. `saved-view-revert` removes only unchanged files that
the WOM writer created and refuses human drift.

See
[`wom-kit/docs/saved-view-write.md`](wom-kit/docs/saved-view-write.md) and
[`wom-kit/docs/releases/v0.3.302.md`](wom-kit/docs/releases/v0.3.302.md).

## v0.3.301 Letter 112 Real-Use Completion

v0.3.301 is compatible with existing v0.3.300 archives and requires no
automatic migration. External-locator v0.1 records and revert receipts remain
readable; v0.2 writes add optional service/account/occurrence coordinates.

Relative `source-intake-record --source-intake-plan` paths now resolve from
the archive root. New `source-intake-batch` requests can record 1-1,000
metadata-only local plans behind one exact human review gate. Existing capture
approval remains separate.

Before allowing an AI to draft or revise, run `authoring-conventions
--dry-run`. A missing archive-specific declaration is valid but warns the AI
not to invent a durable house format. Unminted drafts should be revised in
place; intentional removal now uses the receipt-backed `discard-draft` and
`discard-draft-restore` paths.

Simple imported tables can now be normalized to GFM tables. Unknown or
ambiguous markup still blocks the whole affected zet and remains unchanged.
Run a complete normalization plan before any approval.

zet-objet links now use `zettel-objet-link` and its exact revert. The objet
must already be manifested and the complete SHA-256 must be supplied. No
existing zet is migrated automatically.

See
[`wom-kit/docs/letter112-completion.md`](wom-kit/docs/letter112-completion.md)
and
[`wom-kit/docs/releases/v0.3.301.md`](wom-kit/docs/releases/v0.3.301.md).

## v0.3.300 Letters 098-111 Integrated Completion

v0.3.300 is compatible with existing v0.3.299 archives and requires no
automatic migration. The new locator, relation-judgment, batch-capture, and
markup-normalization records are created only when their new commands are
explicitly used.

Before using markup normalization on a real archive, run
`markup-style-guide` and a complete `markup-normalization-plan`. Unknown
semantic tags must be reviewed rather than deleted. Reference tags need a
reviewed binding to an already-existing locator or edge. If a writer is
interrupted, use `markup-normalization-recovery --mode resume|rollback`
against the retained journal; never remove the journal or hand-edit affected
zets to bypass it.

Relative Objet selection and project-intake staged-folder paths now resolve
from the archive root. Scripts that intentionally relied on the process
working directory should pass an absolute path or update to the documented
archive-relative coordinate.

`operator-feedback-record` now defaults to collision-safe
`--intent create`, so an existing feedback id is never overwritten. Automation
that deliberately updates a record must first run `--intent update --dry-run`,
then replay with the returned `current_record_sha256` as
`--expected-record-sha256`. Omitted title, related-release, and recorded
delivery/acknowledgment timestamps are preserved during that update.

`sequence` is now an active manual-only base edge. Use `continues` for the next
week or installment of the same course/work, and `sequence` for the next
reviewed step in a generic administrative, operational, or life-event process.
Preview and adopt only the needed type in a vendored archive:

```powershell
archive migrate <archive-root> --target base-link-types --link-type sequence --dry-run --format json
archive migrate <archive-root> --target base-link-types --link-type sequence --approve --reviewed-by <actor> --format json
```

The same `--link-type` selection supports `--revert --dry-run` and approved
revert while the adopted record remains equivalent to the base record and no
zettel edge uses it. Custom same-id records and used types block removal.

Register a reviewed non-owner person, institution, team, or role before using
its Principal id as a Zettel edge target:

```powershell
archive principal-register-plan <archive-root> --principal-id company:example --kind company --display-name "<reviewed name>" --dry-run --format json
archive principal-register <archive-root> --principal-id company:example --kind company --display-name "<same name>" --expected-plan-sha256 <sha256> --approve --reviewed-by <actor> --format json
archive principal-list <archive-root> --format json
```

The owner stays in `archive.yml`; reviewed third parties live under
`principals/*.yml`. `archive index` projects both into SQLite. Unregister only
through its plan/approval pair; any live Zettel edge to that Principal blocks
removal.

Recurring occurrences share `facets.recurring_series` without automatically
creating an edge. One occurrence's multi-zet grouping requires an existing
reviewed event anchor before `activity_group` membership. Private Notion
recovery joins must use exact `facets.source_page_id`, never a similarly named
mirror field.

See
[`wom-kit/docs/letters098-111-completion.md`](wom-kit/docs/letters098-111-completion.md)
and
[`wom-kit/docs/releases/v0.3.300.md`](wom-kit/docs/releases/v0.3.300.md).

## v0.3.297 Receipt-Bound Private Objet Generated Index

v0.3.297 is compatible with existing v0.3.296 archives and requires no
archive migration. Run the ordinary rebuild to create or refresh the new
disposable private projection:

```powershell
archive index <archive-root> --format json
archive index-health <archive-root> --dry-run --format json
```

The rebuild validates the complete v0.3.296 private manifest and immutable
receipts, generates deterministic aliases and audience-safe labels, and writes
the inherited public and new four-table private layers in one SQLite
transaction. On Windows, keep every other WOM and non-WOM archive writer
stopped for the complete operation; the rebuild uses the retained mutation
guard and object-then-private persistent-lock order. Non-Windows uses exact
authority snapshot A/B comparison without a substitute lock.

Do not interpret a failed command after the commit boundary as proof that the
database is stale. Output or progress transport failure returns exit code `1`
but does not undo a successful commit. Run fresh `index-health` and trust its
current on-disk evidence.

Private health never creates WAL/SHM files to make a clean WAL database
readable. If the database header advertises WAL but an already coherent
WAL/SHM pair is absent, the private envelope reports
`private_objet_metadata_projection_unavailable` before private query
consumption. Re-run after a coherent pair already exists; do not treat that
closed availability result as proof that the committed index was rolled back.

This release adds no private finder or search result. The generated database
is private and disposable; the manifest and receipts remain authoritative.
Health does not prove objet-byte availability, storage integrity, provider
state, source coverage, external-store completeness, remote backup, or global
privacy cleanliness.

See
[`wom-kit/docs/releases/v0.3.297.md`](wom-kit/docs/releases/v0.3.297.md).

## v0.3.296 Reviewed Private Objet Metadata Registration

v0.3.296 is compatible with existing v0.3.295 archives and requires no archive
migration. The existing private metadata and safe-label schemas remain
normative. The release adds one new CLI-only lifecycle for registering one
human-reviewed private filename observation:

```powershell
archive objet-source-metadata-write <archive-root> `
  --intake <archive-relative-private-json> `
  --expected-intake-sha256 sha256:<64-lowercase-hex> `
  --dry-run `
  --format json
```

Dry-run is cross-platform, content-free, and writes no lock, directory,
manifest, journal, receipt, database row, or index. Approval is supported only
on Windows 10 version 1607 or newer and Windows 11, on a local NTFS volume. It
requires the exact intake and plan digests, a safe `operator:` token, explicit
private review, and `--affirm-external-writers-quiescent` while every other WOM
and non-WOM archive writer stays stopped for the complete operation.

Approved registration appends one canonical private row and publishes one
immutable private or restricted receipt. Exact replay, rollback, and
interrupted-append recovery are supported through the retained Win32
identity/lock/journal profile. This is process-interruption evidence, not proof
of sudden-power-loss directory-entry or volume-metadata durability.

If terminal release of a retained raw Windows handle remains unproved after
three consecutive close-and-validity cycles, the writer fail-stops with process
exit code 74 instead of returning a normal JSON result. Run a fresh dry-run
afterward to reclassify the current state; the failed invocation does not claim
whether the affected residue survived.

The release performs no archive migration, private index ingestion, private
finder query, database/index write, object-byte read, provider/network/
credential-store call, external-store scan, MCP write, or UI change. A
registered name is therefore not searchable yet, and registration does not
prove object-byte availability or source coverage.

See
[`wom-kit/docs/releases/v0.3.296.md`](wom-kit/docs/releases/v0.3.296.md).

## v0.3.295 Private Objet Metadata Contract

v0.3.295 requires no archive migration and writes no private metadata. It
publishes two schemas plus a pure normalization and projection reference
module for later approved writers and finders.

The wheel now depends on `unicodedata2==17.0.1`; normal package installation
resolves the platform dependency automatically. The installed-wheel checker
requires both distribution version `17.0.1` and Unicode data version
`17.0.0`.

The existing `objet-rediscovery-plan` private metadata layer remains
`not_implemented`. Its new reason means that the contract exists while the
approved writer, receipt-bound index, and private query remain absent. Do not
interpret this release as real private-name ingestion or search.

See
[`wom-kit/docs/releases/v0.3.295.md`](wom-kit/docs/releases/v0.3.295.md).

## v0.3.294 Checked-Layer Objet Rediscovery

v0.3.294 requires no archive migration and rewrites no zettel, index,
manifest, receipt, metadata, Runtime Skill installation, or `AGENTS.md`.

Before claiming that a preserved original or objet does not exist, run:

```text
archive objet-rediscovery-plan <archive-root> <query> --dry-run --count-total --format json
```

The command is intentionally a privacy-safe evidence plan, not a private
filename finder. It does not echo the query or search rows. It reports all ten
fixed rediscovery layers and preserves ordinary index `complete` and
`truncated` values under `index_search`. Each of the five index channels gets
its own bounded probe even when an earlier channel fills the result limit. In
v0.3.294, unimplemented or unchecked layers mean the result remains `search_incomplete`,
`rediscovery_complete: false`, and `negative_claim_supported: false`.

Before public release, rebase this candidate onto the exact public v0.3.293
merge commit and rerun the full suite and clean-wheel verification.

See
[`wom-kit/docs/releases/v0.3.294.md`](wom-kit/docs/releases/v0.3.294.md).

## v0.3.293 Runtime Guidance Readiness

v0.3.293 requires no archive migration and rewrites no zettel or `AGENTS.md`.
To check one Codex repository explicitly, run:

```text
archive runtime-guidance-readiness <archive-root> --host codex --scope repo --repo-root <repo-root> --format json
```

Ordinary `runtime-context` and `ai-start-here` deliberately return
`not_checked`; they do not inspect host installation state. A ready file check
still reports host consumption as `not_proven`. When Skill work is needed,
preview the reported `runtime-skill-install --dry-run` command and keep its
existing approval lifecycle separate.

Operator feedback guidance now follows plan dry-run, ledger dry-run, human
review, record dry-run, and explicit reviewed approval. No external delivery
or human receipt is inferred.

Before public release, rebase this candidate onto the exact public v0.3.292
predecessor and rerun full and clean-wheel verification.

See
[`wom-kit/docs/releases/v0.3.293.md`](wom-kit/docs/releases/v0.3.293.md).

## v0.3.292 Objet Tie-Count Consistency

v0.3.292 requires no archive migration and rewrites no zettel.

Overview and catalog `tie_summary.referenced_objets_count` now count distinct
structured frontmatter objet relationships from the existing `assets`,
`source_refs`, and `source_intake` fields plus canonical edge target fields
`target`, `target_id`, and `zettel_id`. Only a complete
`sha256:<64 hex>` or `objet:sha256:<64 hex>` target is accepted; aliases are
normalized and deduplicated by digest.

The count intentionally does not scan the body:

```text
tie_summary.referenced_objets_count
  = distinct structured frontmatter objet relationships

zettel-objet-links.count
  = distinct objet IDs discovered across valid frontmatter and body
```

Therefore a body-only reference can make `zettel-objet-links.count` larger
than the overview or catalog count. Catalog output remains `body_read: false`.
Redacted overview and catalog results remain zero before private relationship
existence is inspected or exposed.

An edge target that contains an object-ID marker but is not one complete
canonical object ID is also rendered as the fixed `<redacted-reference>`
placeholder in overview and catalog edge previews. This prevents partial,
suffixed, URL/path-contained, uppercase-prefix, or non-string target values
from being excluded from the count while still leaking through the preview.
Valid object IDs, valid zettel targets, and ordinary safe labels remain
available.

No command, MCP tool, writer, migration, index rebuild, provider call, or
archive mutation is added. Existing automation that interpreted
`tie_summary.referenced_objets_count` as a body-search count should use
`zettel-objet-links` for that broader read-only question instead.

See
[`wom-kit/docs/releases/v0.3.292.md`](wom-kit/docs/releases/v0.3.292.md).

## v0.3.291 Runtime Version Alignment

v0.3.291 changes no archive data and requires no archive migration.

After a project update, the project source mirror and version pin may be
current while the global `archive` command still imports another Python
checkout. Use:

```powershell
archive version <project-or-archive-root> --format json
```

The new `runtime_alignment` block distinguishes an aligned runtime, project
source that must be repaired or updated first, and a self-consistent source
mirror that can be run through a project-scoped bridge. Local paths remain
redacted by default.

On a trusted machine, explicit `--no-redact-local-paths` can return a
structured exact bridge argv only after source package, pyproject, pin, and
wrapper checks and only when `runtime_alignment.integrity.verified` is true.
That local gate also requires real project paths and project-local Git
metadata, direct raw worktree/index/flag agreement, the closed import tree, all
103 synchronized resources, the annotated version tag and matching tagged
versions, and local `origin/main` ancestry. The Python `-I -S` bootstrap binds
the expected commit, tag, wrapper blob, and resource blobs, executes the
wrapper from verified memory, and permits only the `version` command. `-S` blocks
`site`, executable `.pth` lines, and `sitecustomize` before bootstrap; only
after verification are stdlib `sysconfig`'s `purelib` and `platlib` paths
appended without `site.py` processing. The gate disables
replacement objects and lazy fetch, uses no network, and reads no origin URL
value. The bridge removes project aliases from `sys.path`, never inserts
`wom-kit/src`, and uses an exact-object-ID finder only for `wom_kit`; a
post-gate top-level `yaml` or `sqlite3` shadow therefore cannot execute from
the project tree. The bridge runs the project source once. It does not replace
`archive` on `PATH`, update a Python environment, infer
pip/uv/pipx/editable ownership, restart a process, or install the runtime Agent
Skill.

For ordinary work in an active source checkout, do not invoke
`wom-kit/cli/archive.py` directly. From inside `wom-kit/`, use:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli <command> ...
```

or in a POSIX shell:

```bash
PYTHONPATH=src python -m wom_kit.archive_cli <command> ...
```

The direct wrapper is reserved for the exact verified `bridge_argv` or a
pristine-checkout recovery attempt. Its six stable external refusal codes and
fixed `WOM_BRIDGE_RECOVERY_DOC` pointer are documented in
[`wom-kit/docs/version-truth-source.md`](wom-kit/docs/version-truth-source.md#wom-bridge-refusal-codes).

Existing Windows source mirrors need one additional transition safeguard.
When an older checkout used `core.autocrlf=true`, an unchanged `.py` file can
remain in CRLF form even after the new repository attributes require LF.
Approved `project-version-update` now validates cross-platform paths and safe
file/directory transitions, then manually materializes the complete tracked
target commit tree without `git checkout`. It rebuilds the stage-zero index and
verifies raw bytes, flags, versions, the closed tree, and synchronized
resources before pins.

The updater snapshots raw worktree/index/flags instead of calling `git status`,
so configured clean/process filters do not run. Runtime inventories stream
`os.scandir` under fixed caps, and an ignored, noncolliding top-level
`wom-kit/src` shadow blocks before mutation.

The configuration digest binds effective Git config plus exactly
`GIT_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_SSH`, and `GIT_SSH_COMMAND`. It does
not bind the selected `git` executable, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`,
`SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, or other
non-`GIT_*` toolchain/transport environment; keep them trusted and stable for
the approval.
If the digest changes immediately before rollback, WOM skips source/pin
restore, keeps the owned lock, and reports incomplete rollback.

Source and pin snapshots are checkpointed drift detection, not atomic file
compare-and-swap. Windows directory stability does not stop file-content
changes between a check and write. After dry-run, keep external editors,
sync/backup tools, and other Git writers quiescent for the complete transaction,
then pass `--affirm-external-writers-quiescent` with the reviewer on every
approval. The result reports
`external_writer_quiescence_required: true`,
`external_writer_quiescence_affirmed: true`,
`atomic_file_compare_and_swap: false`, and
`checkpointed_change_detection: true`. The v0.2 receipt records
`external_writer_quiescence: {affirmed: true, scope:
complete_project_version_update_transaction}`. True handle/descriptor-bound
file CAS remains future work. Receipt schema v0.1 remains compatible for old
receipts.
`no_change` still requires the exact target tree, synchronized resources, and
all recognized pins to be verified.

The approved v0.3.291 project updater is Windows-only. Windows holds the real
project, source/`.git`, pin, lock, and receipt directory chains without
`FILE_SHARE_DELETE`, so another process cannot rename, delete, or junction-swap
them during the transaction. A missing receipt parent and root are created and
held in order, and the receipt helper requires that held root.

On POSIX, dry-run still returns a complete read-only preview, but its status is
`preview_only_platform_unsupported` and
`write_boundary.approval_platform_supported` is `false`. POSIX `--approve`
fails closed because an open directory descriptor does not stop pathname rename
and the Git/complete-tree transaction is not descriptor-relative end to end.

See [`wom-kit/docs/releases/v0.3.291.md`](wom-kit/docs/releases/v0.3.291.md)
and
[`wom-kit/docs/version-truth-source.md`](wom-kit/docs/version-truth-source.md).

## v0.3.290 Edge Writer Entity-Type Enforcement

v0.3.290 fixes the existing `zettel-edge` safety gate. It requires no archive
migration and does not rewrite an existing edge.

Before this release, the writer confirmed that an edge type ID was active and
that the target existed, but it did not enforce the selected type record's
`from` and `to` entity types. It now treats the source as `Zettel`, a zet
target as `Zettel`, and a manifested objet target as `OriginalObject`, then
requires those endpoint types to match non-empty lists in the active
`types.yml` record.

This means, for example:

```text
continues      accepts a Zettel target
embed          accepts an OriginalObject target
format_variant accepts either target kind
```

Incompatible, missing, malformed, or empty contracts fail before a zettel or
receipt is written. If your archive vendors its own
`zettel-kasten/types.yml`, that file remains authoritative; an invalid local
record is not silently replaced with the packaged definition.

The batch writer inherits the same preflight. No policy change is needed, and
an incompatible candidate cannot become an approved batch write.

Upgrade the WOM-kit wheel normally. Then preview the same human-reviewed edge
with `--dry-run` before approval. See
[`wom-kit/docs/releases/v0.3.290.md`](wom-kit/docs/releases/v0.3.290.md) and
[`wom-kit/docs/zettel-edge-write.md`](wom-kit/docs/zettel-edge-write.md).

## v0.3.289 Exact Wheel Resource Integrity

v0.3.289 strengthens the release gate used before a WOM-kit wheel is
published. It does not change an installed archive or require migration.

The wheel checker now proves that:

- the packaged resource manifest is exactly the reviewed repository manifest;
- the packaged resource set contains every declared resource and no extra one;
- every declared byte count and SHA-256 matches the bytes in the wheel;
- every resource matches the repository's packaged mirror byte for byte; and
- ZIP member paths and manifest JSON are unambiguous and safe.

Malformed archives, duplicate members or JSON keys, unsafe paths, schema
errors, and content mismatches fail through a bounded `WheelCheckError`
instead of exposing a raw Python traceback.
Windows case aliases, forbidden characters, trailing dots/spaces, reserved
device names, and wheel `.data` relocation members also fail closed before
installation can map them onto a verified resource.

This is a release-engineering safety change. It adds no archive write,
migration, command behavior, provider call, or MCP response change. Install
the new exact wheel normally. See
[`wom-kit/docs/releases/v0.3.289.md`](wom-kit/docs/releases/v0.3.289.md).

## v0.3.288 Content-Free MCP Error Boundary

v0.3.288 is a privacy-hardening release for clients that use `archive-mcp` or
`wom-mcp`.

No archive migration is required. Upgrade the client/server wheel together,
then restart the MCP host process so it loads the new server.

Failed tools now return one fixed envelope:

```json
{
  "content": [{"type": "text", "text": "Tool execution failed."}],
  "structuredContent": {"error": "tool_execution_failed"},
  "isError": true
}
```

If a client previously displayed or parsed human exception messages from
`structuredContent.error`, update it to recognize
`tool_execution_failed`. Diagnose the underlying reason locally; the server
no longer sends raw internal details to the MCP client.

Protocol errors also use fixed category messages. Values such as `false`, `0`,
`""`, and `[]` are invalid for request `params` or tool `arguments`; use
`null` or `{}` when no values are needed.

Successful tool results and archive safety rules are unchanged. See
[`wom-kit/docs/releases/v0.3.288.md`](wom-kit/docs/releases/v0.3.288.md).

## v0.3.287 Read-Only Notion Locator Evidence Plan

v0.3.287 adds the next read-only step after the v0.3.277 locator-loss census.
It does not restore any URL. It validates a private, human-reviewed occurrence
mapping against the exact current bytes of canonical Notion-import zets.

Create the evidence file only under the archive's private scratch boundary:

```text
.wom-scratch/notion-locator-evidence/<private>.jsonl
```

Then run:

```powershell
archive notion-import-locator-evidence-plan <archive-root> `
  --evidence ".wom-scratch/notion-locator-evidence/<private>.jsonl" `
  --dry-run `
  --format json
```

Review these fields:

- `aligned_count`
- `blocked_count`
- `coverage_complete`
- `uncovered_affected_count`
- each safe row's `blocker_codes`
- `evidence_file_sha256`
- `plan_digest`

The command joins only through `facets.source_page_id` and binds each row to
the reviewed `expected_canonical_sha256`. It does not use a title, filename,
`index`, external id, URL, or body text as a fallback. Marker count,
frontmatter omitted count, evidence occurrence count, and both complete
ordinal sets must agree.

The output never returns the private source page id, locator, locator
fingerprint, zet id, filename, path, title, body, or context. A false
`coverage_complete` value means the supplied batch is incomplete; it is not a
claim that an uncovered locator is permanently lost.

There is no write or migration command in this release. Do not edit canonical
zets by hand to make a blocked row pass. See
[`wom-kit/docs/notion-import-locator-evidence-plan.md`](wom-kit/docs/notion-import-locator-evidence-plan.md)
and
[`wom-kit/docs/releases/v0.3.287.md`](wom-kit/docs/releases/v0.3.287.md).

## v0.3.286 Manual-Only `format_variant` Edges

v0.3.286 adds one base link type for a narrow case: a human has reviewed two
records and decided that one is another format or rendition of the same
intellectual content. Examples can include a zet and a manifested original
object, or two zets that preserve the same work in different formats.

The stored source is only the human-selected review anchor. It does **not**
claim that the source is older, original, or canonical. WOM's local
`format_variant` is conceptually close to DCMI `hasFormat` / `isFormatOf`, but
it is not an exact mapping to either directional property because this
release does not establish which resource pre-existed.

If the archive has no local `zettel-kasten/types.yml`, no adoption command is
needed: it inherits the new base type from the installed kit.

If the archive vendors its own `zettel-kasten/types.yml`, preview the existing
base-type sync:

```powershell
archive migrate <archive-root> `
  --target base-link-types `
  --dry-run --format json
```

Review `appended_link_type_ids` and `present_not_overwritten`, then approve
only if the result is correct:

```powershell
archive migrate <archive-root> `
  --target base-link-types `
  --approve --reviewed-by <safe-reviewer-id> --format json
```

This sync is append-only and no-clobber. It appends missing base records but
never overwrites a local record with the same id. It intentionally has no
revert. Like the existing migration contract, approval can normalize the
whole YAML file's comments, anchors, flow style, and key ordering, so review
the dry-run and commit the archive only after inspecting the result.

For one human-reviewed pair, preview the existing single-edge writer:

```powershell
archive zettel-edge <archive-root> `
  --from-zettel <review-anchor-zet> `
  --target <alternate-zet-or-objet> `
  --edge-type format_variant `
  --dry-run --format json
```

After verifying both records and the exact direction, repeat with
`--approve --reviewed-by <safe-reviewer-id>`. Store one assertion only; WOM
does not create the reciprocal edge automatically.

The existing edge receipt remains the compensation authority:

```powershell
archive revert-edge <archive-root> `
  --receipt receipts/edges/<edge>.zettel-edge.json `
  --dry-run --format json
```

After the generated index is current, the existing reader can find a
`Zettel -> Zettel` relation from either zettel endpoint:

```powershell
archive related-zets <archive-root> `
  --zettel-id <zet-id> `
  --edge-type format_variant
```

`zettel-edge-batch` cannot auto-write this type. Even if a reviewed policy
lists `format_variant` under `auto_write_edge_types`, the row is returned in
`human_review_queue` with `manual_single_edge_review_required`. Use the
single-edge preview and approval above for each reviewed pair.

This release does not infer `format_variant` from titles, filenames, node
categories, providers, existing `references` edges, or a model. It does not
reclassify or migrate existing edges, write a reciprocal assertion, read a
provider, modify a beta archive, or add an MCP writer. See
[`wom-kit/docs/zettel-edge-write.md`](wom-kit/docs/zettel-edge-write.md) and
[`wom-kit/docs/releases/v0.3.286.md`](wom-kit/docs/releases/v0.3.286.md).

`related-zets` takes a zettel id. A `format_variant` edge may target an
`OriginalObject`, but this release does not add object-id subjects to that
reader.

## v0.3.285 Notion Manifest Index-Title Fallback

No archive migration is required. v0.3.285 changes only title selection for a
new Notion item read from a JSON or YAML manifest. Preview the existing import
command as usual:

```powershell
archive import-external <archive-root> `
  --source notion `
  --export <manifest.json-or-yaml> `
  --dry-run --format json
```

The normal primary title is resolved first. A human-readable title always
wins. Only when that title is identifier-shaped does WOM consider the exact
lowercase top-level string `index` from the same manifest item. The fallback
must pass the existing normalization, whitespace, specificity, identifier,
500-character, local-path, provider-locator, and secret-like metadata checks.
A present unsafe value blocks that item with a fixed content-free code rather
than echoing the rejected value.

Blocked Notion fallback previews withhold all user-derived item identity
fields, including aliases through scalar ids, paths, URLs, hashes, and target
ids. A private `source_page_id` alias is also withheld; if it would become an
explicit or deterministic generated public target filename, the item blocks
with `source_page_id_aliases_public_target_path` before writing. Google Drive
title selection and fallback behavior is unchanged. Shared manifest item-path
failures now use the same hardened, content-free diagnostics for both sources.

The protection covers the seven item identity fields and generated target
path. It is not a byte-global coincidence scrubber: independently supplied
`--export`, target archive, and `--reviewed-by` provenance keeps the existing
truthful result/receipt behavior, so supply those values as intentionally
recorded operational metadata.

After reviewing the current preview and source export, use the existing
approval form:

```powershell
archive import-external <archive-root> `
  --source notion `
  --export <manifest.json-or-yaml> `
  --approve --reviewed-by <safe-reviewer-id> --format json
```

Planning and writes inside this one approved call use one frozen discovery
projection. This prevents an edit during that call from changing the chosen
title beneath the selected zettel id and receipt path. It does not
digest-bind a later approval invocation to an earlier dry-run.

Existing inbox and canonical zets are untouched. The fallback does not apply
to directory-only Markdown or Google Drive imports, and it does not interpret
`Index`, nested `properties.index`, rich-text arrays, `pages.index.jsonl`, a
provider mirror, Notion API data, or `source_page_id`. It creates no
`facets.index` or `source_index_path` and does not improve the generated
search index. See
[`wom-kit/docs/external-imports.md`](wom-kit/docs/external-imports.md).

## v0.3.284 Approval-Gated Activity-Group Membership Removal

No archive migration is required. v0.3.284 continues from the exact private
request and `review_plan_sha256` produced by the v0.3.282 read-only removal
plan. Preview the dedicated removal writer first:

```powershell
archive activity-group-membership-removal-write <archive-root> `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --dry-run --progress --format json
```

After a human verifies every requested removal and every `already_absent`
row, replace `--dry-run` with `--approve`, add a safe `--reviewed-by` value,
and add `--affirm-removals-reviewed`. WOM rebuilds the exact plan under the
shared activity-group writer lock. Changed request or canonical bytes block
the transaction before mutation.

The writer removes only the named event anchor from `ready_to_remove`
participants. It preserves all other membership entries and list shape,
other facets, body, `updated_at`, BOM state, and newline convention.
`already_absent` rows are satisfied without entering snapshots, the mutation
journal, canonical write attempts, or receipt participant entries. When every
row is already absent, no mutation artifacts are created.

Add and removal transactions share one global writer lock and the bounded,
fail-closed scan of both private roots. Their request, journal, receipt, and
recovery contracts remain separate. A handled execution failure restores
exact prior bytes. A process or machine interruption leaves private evidence;
first confirm that the old writer is no longer running, then inspect it with:

```powershell
archive activity-group-membership-removal-recovery-plan <archive-root> `
  --expected-request-sha256 sha256:<request-digest> `
  --dry-run --format json
```

Approve only the exact returned recovery-plan digest:

```powershell
archive activity-group-membership-removal-recover <archive-root> `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-recovery-plan-sha256 sha256:<recovery-plan-digest> `
  --approve --reviewed-by <safe-reviewer-id> `
  --affirm-recovery-reviewed --progress --format json
```

Unknown drift remains `manual_forensic_hold`. Do not delete transaction
evidence or edit canonical zets to force progress. v0.3.284 adds no
membership inference, MCP writer, or removal revert command. See
[`wom-kit/docs/activity-group-membership-removal-write.md`](wom-kit/docs/activity-group-membership-removal-write.md).

## v0.3.283 Activity-Group Retained-Journal Isolation

No archive migration is required. v0.3.283 keeps every existing activity-group
artifact schema at v0.1, keeps the current CLI and aliases, and keeps
AI command-path routing at v0.5.

The approved membership-add writer now checks both direct private request
roots:

```text
.wom-scratch/private/activity-groups/
.wom-scratch/private/activity-group-removals/
```

Any retained add journal or reserved future-removal journal blocks a new add
before the writer lock and again under that shared lock. The scan is bounded
to 5,000 direct entries, does not recursively inspect nested material, and
does not read or echo journal content. An unsafe root or incomplete scan fails
closed.

Completed recovery now requires the immutable receipt to match the retained
journal or lock on all shared fields and ordered participants. The recovery
plan binds the raw receipt SHA-256 and transaction-binding SHA-256, and the
executor verifies them again immediately before deleting transaction
evidence. Missing, malformed, foreign, or mismatched evidence remains in
`manual_forensic_hold`; do not delete it to make another writer run.

No new command, schema file, MCP method, or route version is introduced.
The approval-gated removal writer remains unavailable and is deferred to
v0.3.284. See
[`wom-kit/docs/activity-group-membership-write.md`](wom-kit/docs/activity-group-membership-write.md).

## v0.3.282 Read-Only Activity-Group Membership Removal Plan

No archive migration is required. v0.3.282 does not remove a membership.
After the owner explicitly selects one event anchor and the exact canonical
members from which it may be removed, store a private request under
`.wom-scratch/private/activity-group-removals/` and run:

```powershell
archive activity-group-membership-removal-plan <archive-root> `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --dry-run --progress --format json
```

Review every `ready_to_remove`, `already_absent`, and content-free `blocked`
row plus `review_plan_sha256`. The command reads only the named live canonical
files, removes only the named anchor in candidate bytes, and does not infer
removal from search results, titles, dates, nearby files, edges, or the
generated index.

Keep the request private. v0.3.282 has no approval mode or removal writer, so
preserve the request and digest as review evidence and do not edit canonical
zets directly. See
[`wom-kit/docs/activity-group-membership-removal-plan.md`](wom-kit/docs/activity-group-membership-removal-plan.md).

## v0.3.281 Approval-Gated Activity-Group Membership Write

No archive migration is required. v0.3.281 does not scan for or automatically
add members. Continue from the exact private request and
`review_plan_sha256` produced by v0.3.280:

```powershell
archive activity-group-membership-write <archive-root> `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --dry-run --progress --format json
```

After a human reviews every membership, replace `--dry-run` with `--approve`
and add a safe `--reviewed-by` value plus
`--affirm-memberships-reviewed`. WOM revalidates the request and all
participant bytes under an exclusive lock, preserves verified before-state
snapshots, writes a private transaction journal before the first canonical
change, and publishes an immutable receipt last.

If a process or machine stopped during the transaction, first confirm the old
writer is no longer running. Then use
`activity-group-membership-recovery-plan --dry-run` and approve only the exact
returned recovery-plan digest through `activity-group-membership-recover`.
Unknown or conflicting bytes are never guessed; they enter a manual forensic
hold.

Membership removal remains unavailable. Do not edit canonical zets directly.
See
[`wom-kit/docs/activity-group-membership-write.md`](wom-kit/docs/activity-group-membership-write.md).

## v0.3.280 Read-Only Activity-Group Membership Plan

No archive migration is required. v0.3.280 does not automatically add or
remove any facet. After a human has selected one canonical event anchor and
its exact canonical members, store the private request under
`.wom-scratch/private/activity-groups/` and run:

```powershell
archive activity-group-membership-plan <archive-root> `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --dry-run --progress --format json
```

The anchor must be a canonical `record_note` whose facets include
`record_type: event` and an ISO 8601 `event_start`; a compatible later
`event_end` is optional. The member list is explicit and ordered. WOM does not
infer membership from search results, titles, dates, nearby files, or edges.

Review `ready_to_add`, `already_member`, and content-free `blocked` rows plus
the bound `review_plan_sha256`. Output omits request paths, zettel ids, zettel
paths, titles, facet values, and body text. This release has no write mode.
Keep the private request out of the public repository and do not manually
rewrite canonical files to imitate a future writer. See
[`wom-kit/docs/activity-group-membership-plan.md`](wom-kit/docs/activity-group-membership-plan.md).

## v0.3.279 Read-Only Inbox Pipeline Audit

No archive migration is required. To look for AI-declared inbox drafts whose
metadata contradicts the current `archive create-draft` output shape, run:

```powershell
archive inbox-pipeline-audit <archive-root> `
  --dry-run `
  --format json
```

The command scans bounded top-level `inbox/*.md` frontmatter. Default findings
contain stable ordinals, path SHA-256 values, classification, and reason codes;
they do not contain raw paths, zettel ids, titles, actors, source values, or
body text.

Interpret the classes conservatively:

- `pipeline_shape_consistent` means compatible shape, not proof that the
  official command executed;
- `possible_out_of_pipeline_draft` means an AI-declared draft contradicts one
  or more current deterministic output facts and needs human review;
- `insufficient_evidence` means WOM cannot honestly classify the creation
  path from available metadata.

Full `archive doctor` reports one aggregate warning when possible cases exist,
so `doctor --strict` also fails until the owner reviews the signal. v0.3.279
does not rename, rewrite, delete, mint, promote, or repair any draft. Do not
change a historical file merely to silence the warning. See
[`wom-kit/docs/inbox-pipeline-audit.md`](wom-kit/docs/inbox-pipeline-audit.md).

## v0.3.278 AI Command-Path Routing

No archive migration is required. New archive templates and live read-only
runtime guidance now begin with:

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
```

Read the returned `action_routing` before choosing an archive command.
Search through:

```powershell
archive search <archive-root> <query> --count-total --format json
```

Raw grep and raw SQL are not authoritative WOM search results. Create
AI-assisted drafts only through `archive create-draft` dry-run and the exact
human-reviewed replay; never write Markdown directly into `inbox/`. Draft
approval does not authorize `mint-zet`.

`archive version` still reports local runtime/source/pin and already-fetched
tag truth only. Check an authoritative remote release surface separately
before claiming that no newer release exists. Saved-view recommendations
remain read-only because a persistent saved-view writer is not implemented.

Existing archive `AGENTS.md` files are not rewritten. Owners may review the
new template contract and adopt it separately. See
[`wom-kit/docs/ai-command-path-routing.md`](wom-kit/docs/ai-command-path-routing.md).

## v0.3.277 Read-Only Notion Locator-Loss Census

No archive migration is required. To measure historical Notion provider
locators that were replaced by omission markers, run:

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --dry-run `
  --format json
```

The alias `notion-locator-loss-audit` is equivalent. The command scans the
complete non-redacted Notion-import population while `--max-items` only bounds
returned per-zet summaries.

Compare `body_marker_count`, `frontmatter_omitted_count`,
`count_mismatch_zettel_count`, and the presence/missing counts for
`source_page_id`. Do not treat count agreement as permission to restore URLs.
v0.3.277 reads no source mirror and writes nothing. Count-mismatch zets and
missing join keys need separate evidence review before a later read-only
occurrence-alignment plan. See
[`wom-kit/docs/notion-import-locator-loss-audit.md`](wom-kit/docs/notion-import-locator-loss-audit.md).

## v0.3.276 Approval-Gated Title Revert Recovery

No archive migration is required. If
`zet-title-remap-revert-recovery-plan --dry-run` reports a complete
non-forensic case, first rerun the new executor with the exact case SHA-256,
complete plan digest, fixed action, and `--dry-run`.

Approve only after the original revert process has stopped, all title writers
and editors are quiescent, and a human has reviewed the fresh state:

```powershell
archive zet-title-remap-revert-recover <archive-root> `
  --case-sha256 sha256:<case> `
  --expected-plan-digest sha256:<plan> `
  --expected-action <action> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-recovery-reviewed `
  --affirm-archive-quiescent `
  --format json
```

Do not pass a revert case to the older `zet-title-remap-recover`, hand-edit
the private journal, or delete snapshots to clear a warning. After any
incomplete run, generate a new plan and approval; a stale plan is intentionally
rejected. `manual_forensic_hold` remains non-executable.

The deterministic compensation receipt preserves the original revert
authorization. v0.3.276 does not persist the new recovery approval in a second
receipt. See
[`wom-kit/docs/zet-title-remap-revert-recover.md`](wom-kit/docs/zet-title-remap-revert-recover.md).

## v0.3.275 Read-Only Title Revert Recovery Plan

No archive migration is required. If a v0.3.274 or later title compensation
was interrupted by a process kill, shutdown, or power loss, preserve its
private revert journal, common lock, canonical participants, source and revert
receipts, and every prior-byte snapshot. Then run:

```powershell
archive zet-title-remap-revert-recovery-plan <archive-root> --dry-run --format json
```

The command reruns the complete bounded title evidence audit and maps only
revert journals to one fixed decision: clean unstarted evidence, continue the
already reviewed compensation direction and finalize its receipt, finalize a
missing receipt after every participant reached its prior bytes, clean exact
verified completed residue, or `manual_forensic_hold`.

This command writes and deletes nothing. Every returned case has
`execution_implemented: false` and `safe_to_execute_now: false`. Do not pass a
revert case to the older interrupted-apply recovery executor. A missing common
lock is only reported as a later reacquisition requirement; it is not silently
created. v0.3.275 does not restore bytes, finalize a receipt, or clean
evidence. See
[`wom-kit/docs/zet-title-remap-revert-recovery-plan.md`](wom-kit/docs/zet-title-remap-revert-recovery-plan.md).

## v0.3.274 Approval-Gated Completed Title Revert

No archive migration is required. First rerun and review the complete
v0.3.273 plan for one unchanged completed title-remap receipt. Preview the
exact approved operation:

```powershell
archive zet-title-remap-revert <archive-root> --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json --expected-receipt-sha256 sha256:<reviewed-receipt-digest> --expected-plan-digest sha256:<reviewed-revert-plan-digest> --dry-run --format json
```

Stop the original title writer and every editor. If the receipt and plan
digests still match, approve the exact same operation:

```powershell
archive zet-title-remap-revert <archive-root> --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json --expected-receipt-sha256 sha256:<reviewed-receipt-digest> --expected-plan-digest sha256:<reviewed-revert-plan-digest> --approve --reviewed-by person:<safe-reviewer-id> --affirm-title-reversions-reviewed --affirm-archive-quiescent --format json
```

The command restores each complete verified prior-byte snapshot, preserves the
original apply receipt, and appends a separate immutable compensation receipt.
A caught failure restores the exact applied bytes. A process kill or power
interruption can retain a revert journal and common lock; preserve that
evidence because v0.3.274 diagnoses but does not yet recover a hard-exit revert
transaction. See
[`wom-kit/docs/zet-title-remap-revert.md`](wom-kit/docs/zet-title-remap-revert.md).

## v0.3.273 Read-Only Completed Title Revert Plan

No archive migration is required. Select one completed immutable title-remap
receipt and calculate its exact SHA-256 outside the command. Then run:

```powershell
archive zet-title-remap-revert-plan <archive-root> --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json --expected-receipt-sha256 sha256:<reviewed-receipt-digest> --dry-run --format json
```

The command requires the complete title evidence audit to be healthy, complete,
and clean. It verifies that every current canonical file still matches the
receipt's applied state, every prior-byte snapshot and manifest record remains
valid, and each transition was exactly title-only. It writes and deletes
nothing.

Do not copy prior snapshots over canonical zets by hand. v0.3.273 produces
review evidence and a complete plan digest but does not implement the approved
revert writer. Keep the source receipt and snapshots immutable. See
[`wom-kit/docs/zet-title-remap-revert-plan.md`](wom-kit/docs/zet-title-remap-revert-plan.md).

## v0.3.272 Approval-Gated Interrupted Title Recovery

No archive-wide migration is required. First generate and review the complete
read-only v0.3.271 recovery plan. Preview one exact executable case:

```powershell
archive zet-title-remap-recover <archive-root> --case-sha256 sha256:<case-digest> --expected-plan-digest sha256:<complete-plan-digest> --expected-action <fixed-action> --dry-run --format json
```

If the case, plan digest, and action are still exact, stop the original writer
and every editor, review the fixed recovery direction, then approve:

```powershell
archive zet-title-remap-recover <archive-root> --case-sha256 sha256:<case-digest> --expected-plan-digest sha256:<complete-plan-digest> --expected-action <fixed-action> --approve --reviewed-by person:<safe-reviewer-id> --affirm-recovery-reviewed --affirm-archive-quiescent --format json
```

The command can clean a prepared transaction, restore an uncommitted partial
or fully applied title batch to verified complete prior bytes, or clean exact
verified completed residue while preserving its immutable receipt.
`manual_forensic_hold` is never executable.

Do not reuse approval after a failed or interrupted run. Generate a new plan:
successful prior-byte restores stay restored, remaining evidence is retained,
and the previous plan digest becomes stale. v0.3.272 does not resume an apply,
create/finalize a receipt, delete prior-byte snapshots, or revert a completed
title change. See
[`wom-kit/docs/zet-title-remap-recover.md`](wom-kit/docs/zet-title-remap-recover.md).

## v0.3.271 Read-Only Title Recovery Plan

No archive migration is required. After running the v0.3.270 evidence audit,
use the new read-only plan for retained title-remap transaction journals:

```powershell
archive zet-title-remap-recovery-plan <archive-root> --dry-run --format json
```

The plan maps each complete retained case to one fixed action: cleanup of an
unstarted transaction, rollback of an uncommitted partial or fully applied
title batch to verified prior bytes, cleanup of exact verified completed
residue, or `manual_forensic_hold`. It blocks if the source audit or returned
case set is incomplete.

The command writes and deletes nothing. Its action is a review decision, not
authority to edit the archive. Preserve every receipt, journal, common lock,
and prior-byte snapshot. v0.3.271 does not execute recovery and does not revert
a completed title receipt. Keep v0.3.271 or newer when reviewing this plan.
See
[`wom-kit/docs/zet-title-remap-recovery-plan.md`](wom-kit/docs/zet-title-remap-recovery-plan.md).

## v0.3.270 Read-Only Title Evidence Audit

No archive migration is required. v0.3.270 understands the v0.3.269
title-remap receipt, transaction journal, prior-byte snapshot, and common-lock
evidence:

```powershell
archive zet-title-remap-receipt-audit <archive-root> --dry-run --format json
```

Run it after a completed title write, after an unexpected exit, or before
planning any recovery. It verifies bounded receipts against current canonical
file/title/body hashes and prior-byte object-manifest evidence, then classifies
retained journals as `prepared`, `partially_applied`,
`fully_applied_receipt_missing`, `divergent`, or `stale_completed`.

The command writes and deletes nothing. Do not hand-edit or delete a reported
receipt, journal, lock, canonical participant, or snapshot. v0.3.270 does not
recover, finalize, clean up, or revert title changes. Keep v0.3.270 or newer
when interpreting this evidence. See
[`wom-kit/docs/zet-title-remap-receipt-audit.md`](wom-kit/docs/zet-title-remap-receipt-audit.md).

## v0.3.269 Approved Title Remap Write

No archive-wide migration is required. The release adds a separate
approval-gated writer after the existing read-only title plan:

```powershell
archive zet-title-remap-plan <archive-root> --proposal .wom-scratch/title-remap/<private>.jsonl --max-items 5000 --dry-run --format json
archive zet-title-remap-write <archive-root> --proposal .wom-scratch/title-remap/<private>.jsonl --expected-proposal-sha256 sha256:<proposal-digest> --expected-plan-digest sha256:<plan-digest> --max-items 5000 --dry-run --format json
```

The second command still writes nothing. Review its result, then rerun the
unchanged candidate with the returned `--expected-write-plan-digest`,
`--approve`, a safe `--reviewed-by`, and
`--affirm-titles-reviewed`.

Before the first canonical change, WOM preserves and verifies the complete
original bytes of every participant as content-addressed objects. The writer
replaces only the single top-level YAML `title` scalar, preserves every other
frontmatter value and body byte, and writes a private text-free receipt last.
A caught failure restores exact original bytes. A hard exit can leave a mixed
batch plus a private transaction journal and common lock; do not delete or
hand-edit those retained files.

v0.3.269 records interruption evidence but does not itself audit or revert
title-remap batches. v0.3.270 adds the read-only audit, v0.3.271 adds a
read-only fixed recovery decision, and v0.3.272 adds one approval-gated
interrupted-case executor. Completed-title revert remains later work. Older
WOM-kit versions can still read successfully changed canonical Markdown, but
they do not understand the new receipt/journal evidence. Keep v0.3.272 or newer for this
workflow. See
[`wom-kit/docs/zet-title-remap-write.md`](wom-kit/docs/zet-title-remap-write.md).

## v0.3.268 Title Remap Usability

`archive zet-title-remap-plan` remains a read-only proposal validator. This
release does not authorize or perform canonical title writes.

The proposal title ceiling is now 2,000 Unicode characters rather than 200.
The schema id stays `wom-kit/zet-title-remap-proposal/v0.1`; the larger
`maxLength` is a backward-compatible relaxation.

Whitespace is never silently normalized. A title must be one line, use only
U+0020 SPACE as whitespace, and contain no leading, trailing, or consecutive
spaces. Line breaks report `title_contains_line_break`; tabs, NBSP, other
Unicode whitespace, and space-placement problems report
`title_contains_non_normalized_whitespace`.

Blocked private/sensitive values now report only fixed
`matched_safety_rules`, never the matched value:

- `local_absolute_path`
- `private_provider_url`
- `credential_assignment_or_private_key`
- `token_shaped_value`

Ordinary public HTTP/HTTPS title URLs are allowed with
`title_contains_public_web_url`. Bare topic words such as `password` do not
block. Proposal-path and size mistakes expose only allowlisted fixed safe
codes; unexpected and archive-root failures remain redacted.

When no trustworthy automatic source title exists, a human may write and
review a specific title with `basis: human_written`, refresh the expected
canonical file SHA-256, and rerun the complete plan. WOM does not invent that
text. See
[`wom-kit/docs/zet-title-remap-plan.md`](wom-kit/docs/zet-title-remap-plan.md).

## v0.3.267 Approval-Gated Abstract Recovery Executor

No bulk archive migration is required. The release adds one single-case CLI
writer for a retained v0.3.265+ abstract transaction journal:

```powershell
archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run --format json
archive zet-abstract-backfill-recover <archive-root> --operation <apply|revert> --basis-sha256 <case.sha256> --expected-plan-digest <plan.sha256> --expected-action <action> --dry-run --format json
```

Preview first. Approval additionally requires a safe reviewer,
`--affirm-recovery-reviewed`, and `--affirm-archive-quiescent`. The executor
reruns the complete bounded plan under a recovery-only OS advisory guard and
acts only when the complete plan digest, basis, action, receipt state, and every
participant hash still agree.

Interrupted apply moves only back to exact journaled before hashes. Interrupted
revert moves only forward to exact journaled after hashes and then create-new
writes and verifies the deterministic revert receipt. Prepared or verified
completed residue removes only its matching lock and journal. Manual forensic
hold, divergence, missing participants, unsafe locks, truncated plans, and an
occupied but unverified final receipt never execute.

The executor does not prove archive quiescence. Its guard coordinates recovery
executors only; external editors, older WOM versions, and ordinary
different-basis writers remain outside it. Stop the old process and all writers
before affirming archive quiescence.

Recovery does not reverse already completed safe-direction writes when a later
step fails. The retained journal and lock record progress for a fresh plan and
fresh approval. Recovery-produced revert receipts therefore truthfully record
`rollback_on_runtime_failure: false`. v0.3.267 relaxes that v0.1 schema field
from `const: true` to a boolean. Every older receipt with `true` remains valid,
but v0.3.266 and older reject a new recovery-produced receipt. After creating
one, keep WOM-kit v0.3.267 or newer for receipt audit. This is a one-way reader
compatibility gate.

## v0.3.266 Read-Only Abstract Recovery Decisions

No archive, zet, receipt, journal, proposal, or index migration is required.
The release adds one read-only command:

```powershell
archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run --format json
```

It reads v0.3.265 transaction journals and the existing bounded receipt/lock
audit, then recommends cleanup, apply rollback, revert forward completion or
receipt finalization, or manual forensic hold. It writes and deletes nothing.

The result is a decision document, not permission to edit files by hand. Every
case reports that the recovery executor is not implemented and that a fresh
recovery approval plus immediate state revalidation will be required. Continue
to retain interrupted journals and locks.

The command is safe to run against an older archive with no journal: it returns
`no_recovery_needed`. Older WOM-kit versions simply do not provide the new
command because v0.3.266 creates no new archive artifact.

## v0.3.265 Durable Abstract Batch Journals

No existing archive, zet, index, or receipt migration is required. The release
adds no command or approval flag. It changes what happens internally when these
two existing approved operations run:

```powershell
archive zet-abstract-backfill-write <archive-root> ... --approve
archive zet-abstract-backfill-revert <archive-root> ... --approve
```

Before either command changes its first canonical zet, it now writes a private
transaction journal under `.wom-scratch/abstract-backfill/`. The journal stores
the exact participant ids/paths and before/after hashes, proposal or source
receipt hash, final receipt path, and review authority. It stores no body or
abstract text.

The apply lock and journal are keyed by proposal SHA in the shared
`.wom-scratch/abstract-backfill/` root. Two byte-identical copies of one
proposal therefore contend on the same lock even when their filenames or nested
directories differ.

Normal success removes the journal after the immutable receipt is written and
verified. A complete in-process rollback removes it after every participant is
verified restored. A process kill or incomplete rollback retains the journal and
the existing lock.

Inspect retained evidence with the existing read-only command:

```powershell
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --format json
```

The audit now reports whether the batch was prepared but not started, partially
applied, fully applied with its receipt missing, externally diverged, or
completed with stale cleanup files. It does not print the private ids, paths,
reviewer, journal digest, body, or abstract.

Do not delete a retained journal or lock merely to make the audit green. This
release diagnoses the interrupted state but does not automatically resume,
finish, write a missing receipt, or roll it back. Preserve the evidence for a
later recovery release or a deliberate forensic decision.

New receipts set the existing `crash_recovery_journal_written` field to `true`;
v0.3.265 continues to validate older receipts whose field is `false`. If you
have run an approved abstract batch with v0.3.265, later audit and revert
operations must use v0.3.265 or newer. v0.3.264 and older enforce `false` in the
v0.1 receipt schema, reject the new `true` receipts as invalid, and therefore
cannot audit or revert those batches. This is a one-way tool-version gate even
though no archive migration is required.

Windows retains the v0.3.264 boundary: files are atomically created/replaced, but
the directory entry cannot be `fsync`ed, so a process kill is covered while a
sudden power loss is not claimed durable.

## v0.3.264 Durable Canonical Writes

No archive, zettel, index, receipt, or schema migration is required. No command
changes its output shape or its success/failure result, and no file content
changes. Two mechanical things do change: a write to a missing parent
directory now creates it instead of failing, and a locked destination is
retried briefly before the same error surfaces. An atomically replaced file
is also a new inode, so hard links to a zet are not preserved and the file
takes fresh default permissions.

This release is entirely about what happens when a write is interrupted. Until
now, every canonical zet mutation went through a helper that renamed a temp file
into place without first forcing the data to disk, so a power loss could leave an
empty or truncated zet where a complete one had been. Two writers to the same zet at the same
time also collided — and not for the reason it first appeared: the contended
thing is the destination, not the temp file, because Windows refuses to replace a
file anyone holds open. The rename is now retried briefly before giving up, which
also covers the commoner single-writer case where a virus scanner or search
indexer has the zet open. Both are fixed.

Nothing you run changes. There is no new command and no new flag. The bytes
written are identical to before — a regression asserts that specifically.

One housekeeping note: if a write was interrupted it may leave a hidden temp file
next to a zet, named `.<name>.<random>.tmp`. This release does not sweep those —
deleting files next to a canonical zet on a name pattern is a bigger decision
than this change earns. Every write path cleans up its own temp file on the
normal and error paths.

Two limits worth knowing. The directory entry is flushed after the rename on
Linux and macOS but not on Windows, which cannot open a directory for that
purpose — so on Windows a power cut immediately after a successful write can
still leave the previous content, though never a torn file. And each write now
costs one extra disk flush; on a bulk migration over thousands of zets that is
measurable (roughly 1-2 ms per zet on local SSD, hardware dependent, more on network storage).
That is the price of not losing a zet, and it is paid per write rather than
batched.

## v0.3.263 Reviewed Title Remap Plan

No archive, zettel, index, receipt, or schema migration is required, and no
existing command changes behavior.

This release adds one read-only command:

```powershell
archive zet-title-remap-plan <archive-root> --proposal <private.jsonl> --dry-run
```

v0.3.262 told you how many canonical zets have an imported page id where a name
should be. This checks the replacement names you already have. You supply a
private JSONL file under `.wom-scratch/title-remap/`, one row per zet, authored
against the shipped `zet-title-remap-proposal.schema.json` contract. Every row
needs all five fields — the `schema` marker is required and a row without it is
rejected:

```json
{"schema":"wom-kit/zet-title-remap-proposal/v0.1","zettel_id":"zet_import_notion_a1b2c3d4e5f60718","expected_file_sha256":"sha256:<64 hex>","title":"2026 startup club test results","basis":"source_export_property"}
```

`basis` is either `source_export_property` or `human_written`, and
`expected_file_sha256` is the hash of that zet as you last saw it.

Nothing is written. The command reports which rows are ready for a human to
review and which are blocked, and why. It reads each named canonical zet in
full — body included — in order to hash it, so this is a wider read than the
v0.3.262 census, which was frontmatter-only.

Three refusals are worth knowing about in advance:

- A zet whose current title is a name a human chose is refused. This command
  repairs imported identifiers and is not a general title editor.
- A replacement that is itself an identifier is refused.
- A replacement that would fail the promotion checklist's "specific enough"
  rule is refused.

A row also blocks if the zet changed after you built the proposal, so a plan is
never made against content you did not look at. A replacement that would be
flagged again by `zet-title-readiness` — including one that equals the record's
own imported identifier — is refused for the same reason.

Unlike the readiness commands, a blocked row makes the command exit 1. This is a
plan that either fully validates or does not. The command also exits 1 when the
proposal is empty, when it has more rows than `--max-items` allows (the default
is 500, so a mapping of a few thousand rows needs a higher value or splitting),
or when `--max-items` is itself out of range.

The approved write, its receipts, and the revert path come in later releases.

## v0.3.262 Identifier-Title Census

No archive, zettel, index, receipt, or schema migration is required, and no
existing command changes behavior.

This release adds one read-only command:

```powershell
archive zet-title-readiness <archive-root> --dry-run --format json
```

It reports how many canonical zets have a title that is really an imported page
id rather than a name. Import batches can copy such a title faithfully from the
source record, and nothing existing flags it: the schema accepts any string as a
title, and a long hex value passes the promotion checklist's specific-enough
test.

The command reads canonical frontmatter only — the title and the imported
identifier facets, not the abstract or the body — writes nothing, and never
prints a title or identifier value. Because a zet's id and filename are minted
from its title, an attention row withholds its own `path` or `zettel_id` when
that value would reproduce the offending title, and reports how many it withheld.
A zet whose frontmatter could not be read, or whose title was suppressed, is
counted separately and keeps the archive from being called ready. It requires
`--dry-run` and exits 1 without it; a `needs_attention` finding still exits 0.

It does not fix anything. A reviewed bulk retitle is a separate approval-gated
flow that will ship across its own releases.

## v0.3.261 Honest Search Coverage

No archive, index, receipt, or schema migration is required, and no index
rebuild is needed for this release.

`archive search`, its default text output, and the MCP `archive_search` tool
now report their own coverage: `truncated`, `complete`, `returned`,
`total_matches`, `total_matches_known`, `matches_by_type`, `limit_applied`, and
`limit_ceiling`. Until now the result reported only how many rows it returned,
so a capped page looked exactly like a complete answer.

Knowing that more matches exist stays free. Knowing exactly how many now needs
`--count-total` (or `count_total` on MCP), because that requires a full scan of
each searched table. A result set that is not truncated already reports its
exact total.

Existing callers keep working. `count`, `query`, and `results` are unchanged,
matching behavior and ordering are unchanged, and the 100-result ceiling is
unchanged — it is now reported rather than silent.

If you have automation that treated `count` as a total, switch it to
`total_matches` and check `truncated` before concluding that a result set is
everything the archive holds.

## v0.3.260 Cross-Platform Release Verification

No archive, zettel, index, receipt, or schema migration is required. Command
names, arguments, output shapes, and exit codes are unchanged.

This release adds the project's first continuous-integration workflow and fixes
the two cross-platform defects it found. The packaged resource manifest is
regenerated: it contains the same 91 entries with identical byte counts and
SHA-256 values, and only their order changed, so an installed wheel behaves
exactly as before.

One behavior difference is worth knowing. Passing a Windows-style traversal
argument such as `..\report.json` to `--prompt-boundary-report` now returns the
fixed "must not contain path traversal" message on Linux and macOS, where it
previously fell through to a raw file-not-found error. Windows behavior is
unchanged, and ordinary relative paths are unaffected.

If you maintain a fork, note that `sync_package_resources.py` now sorts sources
on the archive-relative POSIX string. Regenerate your manifest once so it stops
depending on the platform that produced it.

## v0.3.259 Completed-Result Terminal Semantics

No archive, index, result, or receipt schema migration is required. Command
arguments and normal JSON/text output remain compatible.

When `archive index` or `archive index-health` has already computed its result,
terminal delivery without `--output` is now best effort. A broken pipe, closed
stdout/stderr stream, or console encoding failure no longer overrides the
computed exit code. A committed successful rebuild remains exit 0; a completed
quarantining rebuild or stale/incomplete health result remains exit 1.

This does not make terminal text durable. For unattended or long-running work,
continue to pass `--output .wom-scratch/diagnostics/<name>.json` with a reviewed
archive-relative path and inspect the complete-only saved result. Errors that
happen before a service result exists remain errors and are not swallowed by
this change.

After upgrading:

1. Run `archive version <project-or-archive-root> --format json` and confirm
   `0.3.259`.
2. Keep using `--output` for operations whose result must survive terminal
   transport loss.
3. Treat the process exit code as the command result only after distinguishing
   it from whether terminal text was actually observed.

## v0.3.258 Bounded Object-Storage Transport

No archive, object-manifest, receipt, or provider schema migration is required.
Existing object-storage commands, credential references, key strategies, tier
gates, and multipart settings remain compatible.

The default S3-compatible sender now streams a single path PUT in replayable 1
MiB chunks under its exact signed `Content-Length`. Whole-object verification
GETs are also streamed; only SHA-256, byte count, and completeness evidence are
kept. Control and provider-error responses are capped at 64 KiB, automatic
redirects are disabled, and authority-bearing multipart XML must reach a proven
message boundary before WOM-kit trusts it.

Remote evidence is stricter after this upgrade. HEAD and whole-object GET must
be HTTP 200, only HEAD 404 proves absence, and missing or contradictory proof is
`unavailable`. An unavailable provider response no longer authorizes an
implicit repair PUT, adopt, skip, or conflict claim. CompleteMultipartUpload
`200 + <Error>` is treated as failure and its upload is aborted before retry.

WOM-kit also stops issuing unconditional object DELETE after mismatch. A GET
proves the generation read, but a correct concurrent replacement could occupy
the same key before deletion. A failed verification may therefore leave a
correct or unproven remote object present. Investigate first; cleanup requires a
future generation/ETag-conditional provider contract.

After upgrading:

1. Run `archive version <project-or-archive-root> --format json` and confirm
   `0.3.258`.
2. Re-run a one-object local upload plan and byte verification in dry-run mode.
3. Keep the first live provider run tiny and use the existing reviewed tier
   gate.
4. If verification reports failure or unavailability, do not delete the remote
   key based only on that result.

## v0.3.257 Strict Revision Approval Snapshots

No archive schema migration is required. Existing valid revision and exact
restore commands, private proposal locations, receipts, and plan schemas remain
compatible.

This release changes when revision and restore evidence is allowed to exist.
Before WOM-kit computes a file hash, semantic hash, equality result, plan
digest, or approved candidate, the complete canonical zet or private proposal
must pass a bounded regular-file read plus UTF-8, frontmatter, schema, zet id,
archive id, and canonical-status validation. Rejected bytes are represented by
fixed blocker codes and null/false evidence fields; they are not fingerprinted
as if they were trusted zet state.

Approval-bound YAML also rejects duplicate keys, non-string keys, cyclic
aliases, excessive nesting or expansion, YAML-only set/binary values, and
non-finite numbers. The existing compatibility treatment for unquoted YAML
timestamps remains: they are normalized to ISO strings before schema checks.
The tolerant parser used by import and capture workflows is unchanged.

After upgrading:

1. Create or review the private revision/restore proposal as usual.
2. Run a fresh `archive zet-revision-plan ... --dry-run --format json` or
   `archive zet-revision-restore-plan ... --dry-run --format json`.
3. If the result is blocked, repair the proposal or source zet deliberately.
   Do not copy an old digest into a new approval command.
4. Run `archive zet-revision-receipt-audit <archive-root> --dry-run --format
   json` before relying on revision history for another restore.
5. Approve only the new dry-run result and its exact hashes/digests.

This is a validation-ordering release, not a new transaction engine. Canonical
replacement, receipt publication, locks, rollback, and recovery retain their
existing algorithms. Abstract-backfill, reconcile, workpack, approval-handoff,
and the broader recoverable mutation-engine work remain separate maintenance
batches.

## v0.3.256 Fail-Closed Zettel Integrity And Honest Index Health

No archive schema migration is required. Existing valid draft, canonical,
archived, and redacted zets remain compatible. The disposable generated-index
metadata format advances to v0.2, so a v0.3.255 index is not trusted as the
current metadata fast path until it is rebuilt.

This release separates tolerant foreign-input parsing from the stricter
existing-archive content boundary. An archive zet is readable only when it has
supported frontmatter delimiters, a YAML object, and one recognized lifecycle
status. Invalid YAML, delimiter shape, encoding, file access, missing status, or
an unknown status now produces a fixed content-free issue instead of letting
ambiguous bytes become ordinary body text. Search, views, facet reports, and
related-zets also allowlist readable lifecycle statuses, so a legacy generated
index row with a null or unknown status is excluded even before a rebuild.

`archive index` can safely commit a rebuilt index when one or more source zets
are unreadable. Each affected file gets a path/stat-only row with status
`unreadable`; title, id, kind, body, frontmatter, hashes, edges, and facets are
not retained as queryable logical content. The command then returns exit code
1 with `state: completed_with_quarantined_zettels`, `index_rebuilt: true`, and
`index_complete: false`. That means a safe but incomplete generated index was
installed and the source files still need repair. It is neither a complete
success nor an index rollback.

The v0.2 index metadata stores `index_complete` and the quarantine count in the
same transaction. Mint/promotion duplicate approval checks and `validate
--scope` reject an incomplete index. Repair the listed source files and perform
a complete rebuild before either workflow; a live duplicate fallback also
blocks any unreadable canonical candidate instead of silently skipping it.

Even `index_complete: true` is paired with a live path/stat snapshot before
these consumers trust indexed rows. WOM-kit enumerates physical zets and
compares each stored file-size/mtime tuple. If a zet was added, removed, or
changed, mint falls back to live content validation. If enumeration/stat is
unavailable or an unsafe symlink/junction/reparse boundary appears, mint blocks
instead of attempting another potentially incomplete scan. Facet-scoped
validation asks for a rebuild in either case.

After upgrading:

1. Run `archive index-health <archive-root> --dry-run --progress --format json`.
2. If it reports `live_zettel_frontmatter_unreadable_or_invalid`, repair the
   reported archive-relative source files first. Rebuilding cannot repair a
   malformed source zet.
3. Run `archive index` explicitly when health still reports a missing or stale
   generated index. Honor `ok`, `index_complete`, and the process exit code.
4. Run a fresh `index-health` and require `index_state: current` with no live
   inspection issues before treating the generated index as complete.

Quarantine is logical/API sanitization, not forensic secure deletion from
SQLite free pages, WAL files, backups, snapshots, the filesystem, or the source
zet itself.

This release deliberately does not claim every approval-heavy historical
workflow has the same strict validation ordering. Revision/restore,
retire-reconcile, abstract-backfill, and target-workpack follow in v0.3.257.
Bounded-memory default S3-compatible transport follows separately in v0.3.258.

## v0.3.255 Crash-Safe Index Rebuild And Durable Result Capture

No archive migration is required. Existing zets, objets, manifests, receipts,
views, source maps, and generated indexes remain compatible.

This release fixes the generated-index rebuild boundary. `archive index` now
keeps schema setup, old-row deletion, replacement rows, and metadata updates in
one explicit SQLite transaction. If the process stops before commit, the prior
committed index remains available instead of leaving a delete-only result.

Long `index` and `index-health` commands can now add content-free progress with
`--progress` and write one complete private diagnostic with `--output
.wom-scratch/diagnostics/<new-name>.json`. Use a new filename for every run.
The file appears only after a complete command-result boundary; absence after an
interruption means unconfirmed, not success.

After upgrading a project that observed stale or missing index rows, follow this
explicit sequence:

1. Run `archive index-health <archive-root> --dry-run --progress --format json`.
2. Run `archive index` only when health reports a missing or stale index.
3. Run `index-health` again and require exit code 0 plus matching live and
   indexed zettel counts.

`index-health` never rebuilds automatically. The optional output file is local
scratch, not a receipt or canonical archive record. Progress and handled errors
do not echo zet bodies, titles, local absolute paths, or parser excerpts.

## v0.3.254 Independent Audit Follow-Up And Hash-Bound Body Reading

No archive migration is required. Existing zets, objets, manifests, derived
text, handoff receipts, indexes, and default full-body `read-zettel` responses
remain compatible.

Large zet bodies may now be read in bounded JSON pages. Start at cursor zero
with `--body-max-chars`; every nonzero `--body-cursor` must replay the complete
body hash returned by the first page through `--expected-body-sha256`. A changed
body stops the continuation instead of combining two versions. CLI paging
requires `--format json`; omitting all paging options keeps the old full-body
behavior.

`derive-text coverage` and Doctor may now report that pre-normalization
transcript or export bytes are missing from the object manifest when transcoding
changed those bytes. This is a read-only preservation diagnostic, not an
automatic migration. Capture the exact original file as an objet only when the
real bytes are still available and reviewed. Never recreate them from normalized
derived text. A manifest identity by itself is not proof that bytes are still
available locally or remotely.

AI artifact inventory and new session-handoff receipts now state that only the
documented allowlisted roots were scanned. A clean handoff means that bounded
scope and the human conversation review are ready; it does not prove that no AI
artifact exists elsewhere in the archive. Existing valid handoff receipts remain
recognized.

Current public reading guidance uses `zet` for document traversal and reserves
`node` for a subject/archive participant. No schema, command, output key,
receipt, historical release note, or existing archive identifier is renamed.

## v0.3.253 Optional MOW Harness Compatibility Boundary

This section records a historical v0.3.253 documentation-only boundary. Its
external installation, update, and activation guidance was retired in v0.3.306
and must not be treated as current product advice. No archive migration was or
is required. `collab/` and legacy `.mow-harness/` paths remain ignored only as
defensive local-state quarantine so old prompts, installer metadata, or secrets
cannot enter archive records or public Git surfaces.

## v0.3.252 Philosophy Implementation Traceability

No archive migration is required. This release changes documentation and
regression checks only. Existing command behavior, schemas, zets, objets,
receipts, manifests, indexes, and write authority are unchanged.

Use the paired
[English](wom-kit/docs/philosophy-implementation-evidence.md) and
[Korean](wom-kit/docs/philosophy-implementation-evidence.ko.md) evidence maps
when reviewing whether WOM's design philosophy is implemented. Read each row
across all four columns: the philosophy claim, implemented surface, regression
evidence, and honest boundary belong together.

Do not interpret a structural catalog pass as semantic abstract approval, a
receipt as objective truth, or local backup evidence as current remote proof.
Those remain real-use or provider-specific validation boundaries.

## v0.3.251 Honest Local Backup Evidence Status

No archive migration is required. The release adds one read-only JSON status
command and changes no existing manifest or receipt.

Run:

```powershell
archive backup-evidence <archive-root> --dry-run
```

Read the three lanes separately. GitHub and external-database completion remain
unverified because WOM-kit does not yet have a generic provider-confirmed
completion receipt for them. Object-storage coverage counts only valid
`wom_uploaded` locations linked to matching execution receipts.

`receipt_verified_full_coverage_at_recorded_time` means every eligible object
in the completed bounded manifest scan has local receipt evidence for the time
recorded. It does not mean the remote bytes were checked now, and it does not
make the whole WOM backup complete. `declared_uploaded`, a local commit,
configuration, and generated indexes remain insufficient proof.

The command calls no provider or network, reads no objet bytes or zet bodies,
and writes nothing. Resolve invalid/conflicting evidence through the owning
object-storage workflow rather than editing receipts or manifest evidence by
hand.

## v0.3.250 Receipt-Backed Session Handoff

No archive migration is required. Existing operational-context records and
receipts remain valid. New writes use exact UTF-8 bytes; older Windows receipts
that hashed newline-normalized text are recognized as legacy evidence.

Before ending an AI session, first make sure `ops/operational-context.yml`
contains the current mission, completed work, in-progress work, next actions,
blockers, gotchas, and reviewed decisions. Update it only through the existing
preview and approval flow. Then run:

```powershell
archive session-handoff-checkpoint <archive-root> --dry-run --format json
```

Resolve `needs_durable_capture` before continuing. After reviewing the current
conversation and moving important chat-only context into durable WOM artifacts,
preview again with `--confirm-chat-reviewed`. Approve only the exact returned
`state_digest` with `--expected-state-digest`, `--approve`, and `--reviewed-by`.

The receipt is local session-handoff evidence. It is not proof that the host
chat was read by WOM, that every sentence was preserved, or that GitHub, object
storage, or an external database is backed up.

## v0.3.249 Before-Snapshot Restore Proposal Bridge

No archive migration is required. This release adds an optional CLI bridge for
ordinary v0.2 revision receipts created by v0.3.248 or later.

Preview the verified source and private destination first:

```powershell
archive zet-revision-restore-proposal-from-snapshot <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --dry-run --format json
```

Historically, v0.3.249 approval reused the returned `plan_digest` to create an
independent exact copy under `.wom-scratch/revisions/restores/` without changing
a canonical zet. In current v0.4.12, that `--approve` path is fixed closed before
snapshot or target reads; only the dry-run preview remains available. Historical
proposals can still be inspected and audited. Do not hard-link a mutable
proposal to the immutable snapshot or treat materialization as restore approval.

Legacy v0.1 receipts are unchanged and still require complete old bytes from a
separate trusted private backup.

## v0.3.248 Canonical Revision Before Snapshot

No archive migration is required. Existing v0.1 revision receipts remain
valid hash-only history. They cannot gain historical bytes that were not
preserved at the time.

For every new approved ordinary revision, WOM-kit now preserves the exact
prior canonical zet bytes under ignored `objects/sha256/`, registers the local
object-manifest record, and binds that object in a v0.2 revision receipt before
replacing the zet. Handled rollback retains the verified snapshot, and an
interrupted post-write receipt recovery verifies it before completion.

After upgrading, run:

```powershell
archive zet-revision-receipt-audit <archive-root> --dry-run --format json
```

New v0.2 receipts block if their before-snapshot bytes or manifest record are
missing or changed. A green local audit does not prove remote backup: continue
using the chosen object-storage upload and verification workflow for
`objects/sha256/`. Do not add that ignored byte store to Git.

## v0.3.247 Runtime Artifact Primacy

No archive migration is required. Stored zets, objets, edges, manifests,
receipts, schemas, and command authority are unchanged.

Upgrade when the AI operator should receive the artifact-primacy and human-drift
rules directly from the installed `wom-archive` Agent Skill and generated
archive `AGENTS.md`. The runtime now states that canonical means the current
human-reviewed archive state, matching labels never authorize an identity
merge, generated relationship structures remain reading aids, and
contradictions or changed meanings should remain visible with provenance.

If a managed runtime skill is already installed, use the existing
`runtime-skill-install --dry-run` then exact approved update path. Wheel
installation alone still does not modify AI-host configuration or an archive.

## v0.3.246 Artifact Primacy And Human Drift

No archive migration is required. Runtime commands, schemas, stored zets,
edges, manifests, receipts, and generated indexes are unchanged.

This release clarifies the product authority model. Durable local artifacts and
their chronology are primary evidence; entity and graph projections remain
regenerable reading aids. `canonical` means the subject-approved current
archive state, not objective truth, and matching labels do not authorize a
silent identity merge.

Existing archives should not rewrite, merge, or normalize records merely to
adopt v0.3.246. Upgrade when you want package/release identity and public
operator guidance aligned with this design boundary.

## v0.3.245 Top-Level Installation On-Ramp

No archive migration is required. The root English and Korean READMEs now show
the exact current wheel, an isolated `uv tool install`, `archive --version`,
and the separate read-only Agent Skill activation preview before the long
capability inventory.

Existing v0.3.244 installations do not need a host-skill reinstall for runtime
behavior. Upgrade to v0.3.245 when you want package/release identity aligned
with the improved public installation path. Wheel installation still changes
no archive or AI-host configuration by itself.

## v0.3.244 Approval-Gated Agent Skill Host Lifecycle

No archive migration is required. Update WOM-kit, then preview the local Codex
user-scope skill install:

```powershell
archive runtime-skill-install --dry-run --format json
```

Review the returned target state and `operation_plan_sha256`. Approve only the
same plan with a safe `--reviewed-by` id and
`--expected-plan-sha256 <digest>`. Confirm `managed_current` through
`archive runtime-skill-status --format json`. Restart Codex only if the skill
does not appear automatically.

Codex user scope follows the current `$HOME/.agents/skills` convention.
Repository scope requires `--scope repo --repo-root <existing-repo>`. Other
hosts require `--host custom --scope custom --skills-root <explicit-root>`;
WOM-kit does not guess their configuration paths.

An ownership manifest lets future installs perform a verified managed update
and lets `runtime-skill-uninstall` remove only unchanged WOM-owned files.
Unmanaged, malformed, symlinked, or human-edited targets block. Installing the
Python wheel still does not write any host configuration by itself.

See `wom-kit/docs/runtime-skill-install.md` for the beginner workflow, states,
privacy boundary, and uninstall commands.

## v0.3.243 Progressive AI Runtime Skill

No archive migration is required. Restart the AI operator process after
updating WOM-kit so it can discover the new packaged skill resources.

The bundled `wom-archive` skill now follows the Agent Skills package shape:
one short `SKILL.md` with YAML `name` and `description`, five focused task
references, and one preserved complete operator contract for exact advanced
commands. AI operators should read the root first and load only the reference
that matches the current human goal.

The release gate now runs `wom-kit/tools/check_runtime_skill.py`. It rejects
missing or oversized entry instructions, broken or escaping Markdown links,
undiscoverable references, symlinks, identity drift, and missing critical
approval/privacy/trust language. The installed wheel resource manifest carries
the same files byte-for-byte.

This upgrade does not install anything into Codex, Claude, or another AI
host's configuration directory. It also does not create a generated graph or
change WOM authority: reviewed local zet, objet, relation, and receipt records
remain canonical.

## v0.3.242 Self-Contained Python Tool Wheel

No archive migration is required. Restart the AI operator process after
changing the installed WOM-kit tool.

The tagged GitHub release now carries a verified wheel with the runtime
schemas, templates, base zettel-kasten rules, and release identity needed by an
installed package. Existing repository checkouts and project source mirrors
continue to work; they remain the preferred editable source layout.

For an isolated command-line installation, use the exact release wheel:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.242/wom_kit-0.3.242-py3-none-any.whl"
archive --version
```

Plain `pip` users should install the same wheel in a dedicated virtual
environment. Do not run `pip install wom-kit`: WOM-kit has not been published
to PyPI yet. See `wom-kit/docs/python-tool-install.md` for the full beginner
path and safety boundary.

Package installation alone creates no archive and reads no user data. In
v0.4.0 archive onboarding is preview-only: use `--dry-run`; the approval branch
is fixed closed before target/template/provider reads and creates nothing.

## v0.3.241 Selective Freshness Body Reads

No archive migration is required. Restart the AI operator process.

`abstract-freshness` now reads bounded frontmatter for every canonical zet but
opens complete zet bytes only for a valid explicit-abstract target that needs a
current body hash. It re-parses those complete bytes before trusting the
abstract/body pair. Missing, redacted, and unreadable-frontmatter rows remain
attention or excluded rows without unnecessary body reads.

The result adds `canonical_frontmatter_files_scanned`,
`canonical_body_files_read`, `canonical_body_files_not_read`,
`canonical_body_read_policy`, `canonical_scan_mode`, and
`canonical_scan_workers` under `scan`. These fields are additive. Existing
freshness states, evidence lookup, exit behavior, privacy boundaries, and
no-write behavior remain unchanged.

For a large legacy archive, rerun the same read-only freshness command and
compare the new body-read counts and elapsed time. Do not interpret skipped
body reads as body-validation proof; a zet without a valid explicit abstract is
already a review item, and Doctor/validation remains responsible for broader
file health.

## v0.3.240 Scalable First-Read Diagnostics

No archive migration is required. Restart the AI operator process so the new
diagnostic contract and progress labels are visible.

`first-read-readiness` result schema v0.2 separates command completion from
readiness. A completed scan with `state: needs_attention` or
`compatibility_only` now returns `ok: true`, `readiness_met: false`, and process
exit zero. Automation must inspect `readiness_met` or
`readiness.first_read_surface_ready` instead of treating process exit zero as
proof that every explicit abstract exists. Blocked input or execution failure
still returns nonzero.

`abstract-freshness` now scans canonical zets first and opens only evidence
candidate receipts for current explicit-abstract targets. It does not create a
persistent cache. Progress names `stage=1/2` and `stage=2/2`; an ETA of zero
therefore means the current stage ended, not necessarily the whole command.

For a large legacy archive, do not bulk-generate missing abstracts. Follow the
three-zet pilot in `wom-kit/docs/abstract-backfill-pilot.md`, stop after its
verification commands, and report the human review experience before scaling.

## v0.3.239 Approved Exact-Byte Canonical Restore

No archive migration is required. Restart the AI operator process so the new
CLI-only restore writer and mixed-event audit are visible.

First run `zet-revision-receipt-audit --dry-run`. Recover the complete old zet
from a trusted private backup into `.wom-scratch/revisions/restores/`, run
`zet-revision-restore-plan`, and privately compare the current zet, recovered
zet, and selected receipt. Then run `zet-revision-restore-write --dry-run` with
the exact current/proposal/plan hashes. Approval must reuse the returned event
time and write-plan digest, name a safe reviewer, and affirm restore plus
abstract/body-pair review. Add changed-edge review when the plan requires it.

The approved writer uses the same per-canonical lock as ordinary revision
writes and installs the recovered file bytes exactly. It does not rewrite the
historical `updated_at`, YAML, BOM, newlines, frontmatter order, or body. The
new event time is stored in the immutable restore receipt. Handled failure
restores the exact prior bytes; after a process interruption, rerun the same
approved command instead of deleting the lock or copying files manually.

Ordinary and restore receipts now share one chronological event chain. Run the
receipt audit again after completion. A green result is evidence of reviewed
local application, not factual truth, backup completeness, or external sync.

## v0.3.238 Chronological Revision Event Chain

No archive migration is required. Restart the AI operator process so the
updated read-only audit and restore planner are visible.

Run the ordinary receipt audit before preparing any restore:

```text
archive zet-revision-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

The audit now orders each canonical zet's receipts by normalized event time
and requires exact adjacent before/after evidence. An exact repeated state
such as `A -> B -> A` is allowed when the event chain is continuous. Branches,
partial evidence gaps, duplicate event times, and current-tip drift still
block. Complexity is `O(receipt_files log receipt_files + revision_chains +
lock_files)`; canonical targets are still opened at most once per identity.

`zet-revision-restore-plan` now also requires the selected receipt to be the
actual newest event. Matching an older after-state by coincidence is not
enough. This remains read-only: v0.3.238 has no restore writer and grants no
manual-copy authority.

## v0.3.237 Canonical Revision Restore Plan

No archive migration is required. Restart the AI operator process so the new
CLI-only read command is visible. First recover the complete old zet bytes from
a trusted private backup into `.wom-scratch/revisions/restores/`. Do not commit
that scratch file.

Run:

```text
archive zet-revision-restore-plan <archive-root> --receipt receipts/revisions/canonical/<digest>.zet-revision.json --expected-receipt-sha256 <sha256> --restore-proposal .wom-scratch/revisions/restores/<private>.md --dry-run --format json
```

The command requires the whole revision history to be healthy, the current zet
to match the receipt's `after` state, and the recovered bytes to match every
`before` hash. It also reapplies current publication and quality policy to the
old bytes.

`ready_for_human_review` is not permission to restore. v0.3.237 has no restore
writer. Review the current zet, recovered old zet, and receipt privately, and
do not copy the scratch file over the canonical zet by hand.

## v0.3.236 Canonical Revision Receipt Audit

No archive migration is required. Restart the AI operator process so the new
CLI-only read command is visible. After one or more ordinary canonical
revisions, and before handing the archive to another session, run:

```text
archive zet-revision-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

A healthy result means the retained receipts form one continuous hash history
to each current zet and no recognized transaction lock needs recovery. A
completed leftover lock is a warning; a missing-receipt, prewrite, ambiguous,
invalid, or unsupported lock requires inspection. Never delete a lock or edit
an immutable receipt merely to make the audit green.

The command is read-only and content-free in its output. It cannot prove that
a correction is factually true and cannot recreate an old zet from receipt
hashes. Revert therefore remains a separate, future reviewed workflow that
must begin with privately recovered full-zet bytes.

## v0.3.235 Canonical zet Revision Write

No archive migration is required. Restart the AI operator process so the new
CLI writer is visible. MCP deliberately remains read-only for this workflow.

First run `zet-revision-plan` and review the complete private proposal with the
current canonical zet. Pass its four hashes into `zet-revision-write --dry-run`.
Keep the returned `revision_at` and `write_plan.actual_digest`, then reuse both
with `--approve`, a safe reviewer id, `--affirm-revision-reviewed`, and
`--affirm-abstract-body-pair-reviewed`. Add
`--affirm-edge-changes-reviewed` when the plan changes edges.

Approval replaces one canonical zet atomically and creates one immutable
receipt under `receipts/revisions/canonical/`. Runtime failures restore the
exact previous bytes. If the process stops after replacement but before the
receipt, rerun the exact approved command so the private write lock can finish
the receipt without rewriting the zet. The lock is shared by every revision
plan for that canonical zet, so a second plan stops instead of overwriting an
in-progress revision.

Run `archive abstract-freshness <archive-root> --dry-run --format json` after a
successful revision. An applied revision proves only reviewed local
application and receipt, not truth, external synchronization, backup, legal
clearance, or model understanding.

## v0.3.234 Canonical zet Revision Plan

No archive migration is required. Restart the AI operator process so the new
CLI/MCP planner is visible. Prepare a complete private Markdown correction
under `.wom-scratch/revisions/`, then run:

```text
archive zet-revision-plan <archive-root> --zettel-id <safe-id> --proposal .wom-scratch/revisions/<private>.md --dry-run --format json
```

The proposal must preserve WOM-managed identity, creation, lifecycle, and
original creator metadata. It may change reviewed knowledge fields and the
body, but it still needs a safe explicit abstract, valid edges, provenance,
visibility, and no private body locator.

Review `canonical.sha256`, `proposal.sha256`, `proposal.semantic_sha256`,
`plan_digest`, change categories, blockers, and warnings together with the two
private files. The output itself contains no actual zet id, path, filename,
title, abstract, body, custom frontmatter value, reviewer id, provider URL,
absolute path, or secret.

This release deliberately stops before writing. Do not copy the proposal into
the canonical file by hand. The approval-gated atomic writer and immutable
revision receipt are the next release rung. `remint-reconcile` remains a
recovery path for drift that already happened, not the normal correction
authoring workflow.

## v0.3.233 Abstract Freshness Evidence

No archive migration is required. Restart the AI operator process after the
upgrade so the new CLI/MCP surface is visible, then run:

```text
archive abstract-freshness <archive-root> --dry-run --progress --format json
```

Run it after `first-read-readiness` and before the complete private catalog
pass. `fresh` means the current abstract/body hash pair matches retained human
review evidence. `stale` means the body, abstract, or both changed;
`unverified` means WOM cannot reconstruct review evidence; `missing` and
`unreadable` identify structural gaps. Redacted zets are excluded by policy.

New approved mint and legacy promotion receipts add text-free review evidence.
The scanner also recognizes retained v0.3.232 mint snapshots or promotion
sources and existing applied reviewed abstract-backfill receipts. Existing zets
and receipts remain valid and are never rewritten automatically.

Treat every non-fresh row as a human review queue. Output contains no title,
abstract/body text, hash value, receipt path, reviewer id, provider URL,
absolute local path, or secret. A green result proves exact local hash-pair
continuity only, not truth, completeness, usefulness, or model consumption.

## v0.3.232 Explicit Abstract Publication Gate

No archive migration is required. Existing canonical zets and old receipts
remain valid. New drafts may still be saved without an abstract, but a draft
cannot cross into canonical state until a human-reviewed explicit
`frontmatter.abstract` is present.

Before minting, add one normalized single-line abstract of at most 360
characters, then preview the ordinary mint command:

```text
archive mint-zet <archive-root> --path inbox/<draft>.md --dry-run --format json
```

Inspect `first_read_check`. Continue only when its `status` is `ready` and
`ready_for_publication` is `true`. Compatibility fields such as `summary` do
not satisfy this publication rule. Real minting and legacy promotion bind the
full draft SHA-256 and abstract SHA-256, reread one byte snapshot after
dry-run, and stop before any canonical, receipt, or snapshot write if any
draft byte changed or the abstract is missing or invalid.

The check record contains only status, character count, limit, and abstract
SHA-256; it does not echo the abstract text or read the body for this check.
A green result proves structural readiness only, not truth, completeness,
semantic freshness, or model consumption.

## v0.3.231 First-Read Readiness Gate

No archive migration is required. After updating and restarting the operator
process, run:

```text
archive first-read-readiness <archive-root> --dry-run --progress --format json
```

`state: ready` means every non-redacted canonical zet has an explicit
`frontmatter.abstract` and every selected entry has a uniquely resolvable safe
id at the reported snapshot. Compatibility fields remain readable, but produce
`state: compatibility_only` until a human reviews and approves an explicit
abstract. A non-ready result is a repair queue and may exit nonzero even though
the scan completed normally.

The command reads frontmatter only and writes nothing. It does not judge
abstract quality, prove model consumption, inspect objet bytes, call providers,
or grant backfill approval. Run the private complete `zet-catalog-pass` only
after reviewing the readiness result.

## Current Safe Process And Upgrade Check

Today, WOM-kit relies on release notes, backups, `archive doctor --strict`, and
human review for real archive upgrades.

The following read-only check is available:

```text
archive upgrade-check <archive-root> --dry-run --format json
```

It reports doctor, recovery-plan, restore-drill, and upgrade-readiness signals.
It writes nothing, returns `would_change: []`, does not run migration commands,
does not call providers, and is not a migration engine.
The top-level `ok` means the check ran; use `upgrade_readiness.status`
(`ready`, `warnings`, or `blocked`) to decide whether a real upgrade is blocked,
needs more review, or is ready for manual review.

## Frontmatter v0.3 Migration

The current v0.3 frontmatter contract requires these nested fields:

```text
provenance.created_by
provenance.created_in
provenance.source
provenance.derived_from
visibility.scope
visibility.allowed_archives
visibility.source_visibility
```

If an archive was authored from older `wom-kit/zettel-kasten-rules/v0.2-draft`
guidance, run the migration preview before strict v0.3 validation:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json
```

After reviewing the planned per-field changes on a backup or sandbox copy, apply
the migration with:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json
```

The migration is dry-run-first. It only rewrites archive-contained Markdown
zettel frontmatter under `inbox/` and `zettels/`. Clean legacy source objects
are preserved in `source_refs`; ambiguous, unsafe, secret-like, or external path
values block for manual review instead of being guessed.

Use a sandbox copy or backup before testing a real archive upgrade:

1. Copy or back up the private archive control plane.
2. Confirm the object manifests and local objet store are preserved.
3. Read the target release note.
4. Run `archive upgrade-check <archive-root> --dry-run --format json`.
5. Run `archive doctor --strict`.
6. Rebuild generated search with `archive index`.
7. Run a small `archive search` smoke test.
8. Apply any available migration dry-run before a real migration.
9. Commit private archive changes only after reviewing outputs and receipts.

For project-folder work, remember that temporary intake staging is not the
archive of record. Preserve originals as objets, source maps, manifests, zets,
and receipts before any cleanup.

## v0.3.230 Digest-Bound Content-Change Review

v0.3.230 requires no archive migration and runs no reconcile automatically.
It changes the approval contract only when a dry-run reports
`drift_class: content_change`. Restart the operator process after the official
update. You do not need to repeat a full Doctor just to use this patch; rerun
only the affected per-zet dry-runs.

For a BOM canonical and a separate retired-draft mismatch, keep the two reviews
independent:

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --dry-run --strip-bom --diagnostic-only --format json
archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --dry-run --format json
```

When either result is `content_change`, read its `human_review_plan` and
`review_plan_sha256`. The plan orders the archive-relative evidence files and
reports SHA-256 values, changed field or ref names, and fixed instructions
without copying document content into the JSON. A human reviews those files
locally and chooses one decision:

1. `intentional_change`: explain every changed field or ref, then run the exact
   `human_review_plan.commands.approve_if_intentional` command. Replace
   `<actor>` with the named human reviewer. Its content-change form is:

   ```text
   archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --approve --reviewed-by <actor> --content-changed-ack --reviewed-plan-sha256 <review-plan-sha256> --strip-bom --format json
   archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --approve --reviewed-by <actor> --content-changed-ack --reviewed-plan-sha256 <review-plan-sha256> --format json
   ```

2. `unintentional_change`: restore or repair the named content, then rerun that
   target's dry-run. Do not approve the old digest.
3. `uncertain`: stop without writing and ask the human owner. One target's
   success, a classifier label, or a clean Doctor result does not approve the
   other target.

The approval command recomputes the review plan before any write. A missing,
malformed, or stale `--reviewed-plan-sha256` stops the run. Successful
content-change approval records that digest in provenance and the immutable
audit receipt, returns `content_change_ack_required: false`, and reports
`human_review_plan.status: completed`. Existing `format_drift` approval remains
compatible and does not require this new flag.

## v0.3.229 Executable BOM Reconcile Guidance

v0.3.229 requires no archive migration and changes no archive write path. A
`zettel_has_bom` Doctor finding now fills the redacted reconcile dry-run with
the validated id read from canonical frontmatter:

```text
archive remint-reconcile <archive-root> --zettel-id <actual-id> --dry-run --strip-bom --diagnostic-only --format json
```

WOM-kit does not infer the id from the filename. If canonical frontmatter has no
safe id, the finding and hint remain but the suggested command is omitted. This
is a fail-closed signal to repair or review identity metadata, not an invitation
to substitute a guessed selector.

For a BOM finding and a separate retired-draft receipt mismatch, use independent
dry-runs. Neither command writes:

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --dry-run --strip-bom --diagnostic-only --format json
archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --dry-run --format json
```

For the BOM route, stop on `ok: false`, any blocker, `content_change`,
`body_changed: true`, or `approval_requires_content_changed_ack: true`. If the
redacted result is `format_drift`, reports `bom_stripped: true`, and requires no
content-change acknowledgment, run the same BOM dry-run once without
`--diagnostic-only` and review the current content and frontmatter before any
approval. Only then may a reviewer use:

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --approve --reviewed-by <actor> --strip-bom --format json
```

For retired-draft reconcile, `blocked` or `unclassified` means stop.
`format_drift_ready_for_review` may proceed after reviewing every `ref_reports`
row. `needs_content_change_review` is not an automatic approval: inspect the
current canonical and receipt evidence, and use `--content-changed-ack` only
when a named human confirms that the changed bytes are intentional. The two
reconcile targets are independent; success on one does not authorize the other.

## v0.3.228 Actionable Full-Doctor Results And Current-Stage Progress

v0.3.228 requires no archive migration and changes no archive write path. Start
a new process after the official project update, then run the complete
inspection only when archive health evidence is required:

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

The result now includes `doctor_findings`. It keeps complete ERROR/WARN counts
by diagnostic code, up to 100 actionable items, and up to 20 unique suggested
commands. Each item can retain its severity, code, archive-relative path,
message, hint, suggested command, and compatibility target. INFO remains
count-only. `truncated` and `suggested_commands_truncated` say when the bounded
handoff does not contain every item or command.

This is a forward result contract. A saved v0.3.227 `runtime-context` JSON that
contains only severity totals cannot truthfully reconstruct the discarded
codes, paths, and messages. Identifying those old counts therefore requires one
new Doctor run; v0.3.228 prevents that new completed result from losing the
same evidence again.

During `local-profile-secret-safety`, compact heartbeat now reports only safe
current-stage counters:

```text
checked_files=<files visited>
content_scanned=<text-like files scanned>
local_profiles=<local profile files checked>
skipped_dirs=<ignored directories skipped>
```

The previous edge source-load aggregate remains available for its final `done`
line, but it no longer hides the active safety stage. Ordinary files reuse the
directory boundary already verified by the walk; symlinks still use resolved
containment and ignored-target checks. Secret filename, content, and local
profile rules are unchanged.

The synthetic benchmark writes only a temporary fixture and reads no real
archive:

```text
python tools/benchmark_local_profile_secret_safety.py --file-count 5000 --format json
```

On the release workstation, an immediate same-fixture before/after measurement
improved from 20.838 seconds to 11.644 seconds. The public post-change command
completed another run in 13.693 seconds. These are synthetic workstation
measurements, not a promise for archives with different file sizes, storage, or
antivirus behavior.

## v0.3.227 Aggregate Full-Doctor Edge Progress

v0.3.227 adds no archive migration and changes no Doctor diagnostic or read
decision. It changes only how the optional compact progress stream represents
the targeted edge-receipt work introduced in v0.3.225.

The same complete command remains:

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

A fast `edge-receipt-index` now prints start and done. If it remains active for
a 10-second interval, heartbeat may include its safe count. The source-load phase keeps
one aggregate across the complete Doctor run:

```text
sources=<sources loaded so far>
candidates=<candidate receipt documents opened so far>
cache_hits=<source-result cache hits so far>
```

The final `done` line contains the completed totals. WOM-kit does not add a
second broad scan merely to predict the dynamic final source count.

For each individual source batch, use direct Doctor verbose output or a private
progress log. Those events use the `edge-receipt-source-load-detail` stage:

```text
archive doctor <archive-root> --strict --progress --progress-detail verbose
archive doctor <archive-root> --strict --progress --progress-log logs/doctor-progress.jsonl
```

The JSONL can contain detailed local diagnostic timing and should remain
private. The compact stream remains content-free. A synthetic 8,583-source and
21,539-index-event benchmark produced 4 shared compact lines (358 bytes) versus
51,457 verbose lines (about 6.3 MB); its in-memory timing is only a lower bound
for interactive terminal rendering cost.

## v0.3.226 Archive Identity Consistency And Reviewed Repair

v0.3.226 adds no automatic migration. Quick runtime-context, AI start-here,
and Doctor now compare the principal declaration in `archive.yml` with the
identity and ownership core in `archive-identity.yml`. They report a mismatch
instead of silently choosing one file by read order.

Begin with the read-only preview when `identity_consistency.status` is not
`aligned`:

```text
archive identity-reconcile <archive-root> --dry-run --format json
```

Archives created by v0.3.226 `init` or onboarding begin aligned because their
template identity id/display metadata is replaced with the reviewed archive
and principal values. Existing archives are never changed by upgrade alone.

The preview reads only the two control files, writes nothing, and returns field
names and SHA-256 digests without identity values. Principal, archive-id,
scope, or invalid-document conflicts block automatic repair. Only
same-principal display metadata and a missing or template-like identity id can
be proposed.

If the result is `repair_ready`, inspect both source files and use the complete
`approval_command` returned by that exact preview. It requires an attributed
reviewer, an explicit principal-metadata affirmation, and the exact archive,
current identity, and proposed identity digests. Any drift refuses the write.

Approval edits only `archive-identity.yml`, reserializes its YAML, verifies the
result digest, and writes a value-free receipt under
`receipts/identity-reconciles/`. Parsed semantic changes are limited to the
listed fields, but comments or YAML formatting may normalize. A handled
receipt failure restores the exact original identity bytes. After approval:

```text
archive runtime-context <archive-root> --strict --format json
archive doctor <archive-root> --strict
```

## v0.3.225 Targeted Full-Doctor Edge Receipt Index

v0.3.225 adds no archive migration and writes no archive state. In an explicit
full Doctor run, the first historical mint target SHA no longer causes every
edge receipt JSON document to be opened. Doctor now builds one filename-only
index for the run, then opens only receipts named for the mismatched source zet
and legacy receipt paths referenced directly by that zet's current edges.

Progress uses two independent, content-free stages:

```text
edge-receipt-index: <current>/<total>
edge-receipt-source-load: <current>/<total>
```

The first count is the complete receipt filename inventory; the second is the
small candidate set whose JSON is actually loaded for that zet. Neither stage
prints receipt paths, zet ids, edge values, titles, bodies, abstracts, provider
values, or secrets.

Maintainers can reproduce the 8,583-receipt synthetic regression without
reading a real archive:

```text
python tools/benchmark_doctor_edge_receipt_index.py --receipt-count 8583 --format json
```

The benchmark uses a temporary fixture, calls no provider, persists nothing,
and verifies one index build, one target load, and a second-lookup cache hit.
It covers the previously stalled Doctor phase; a real archive should still run
the explicit full Doctor to verify its complete local workload.

## v0.3.224 Quick Runtime Context And No-Repeat Handoff

v0.3.224 adds no archive migration and writes no archive state. CLI and MCP
`runtime-context` are now quick by default. The ordinary command reads bounded
identity, policy, entrypoint, authority, version, and operational-context
metadata without constructing Doctor or walking every zet and receipt:

```text
archive runtime-context <archive-root> --format json
```

Use complete validation only when the task actually needs it:

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

MCP uses the same split: omit `full_doctor` for quick context, or pass
`full_doctor: true` for complete Doctor diagnostics. Both surfaces report
`inspection.mode`, `inspection.full_doctor_run`, Doctor status, and observed
broad reads. Scripts that relied on runtime-context to run Doctor implicitly
must add the explicit full-Doctor option.

An `ai-start-here` result already contains runtime-context. Its compatibility
list `first_commands` now marks that row `already_included` and
`run_required: false`; use `next_commands` and `remaining_ai_runtime_order` for
the executable continuation. The source operational-context record is not
rewritten, but a stale default `Run runtime-context first.` line is no longer
copied into start-here's next-safe-step list.

## v0.3.223 Full-Doctor Receipt Phase

v0.3.223 adds no archive migration and does not change the quick/default
`ai-start-here` behavior from v0.3.222. In the optional full scan:

```text
archive ai-start-here <archive-root> --dry-run --full-doctor --progress --format json
```

heartbeat now carries a fixed content-free `phase` when a mint receipt holds
the same outer count. Examples include `target_file_ref`, `file_hash`,
`target_edge_evolution`, and `edge_receipt_index`. These labels explain the
class of local work without exposing a receipt path, zet path/id, object ref,
edge value, title, body, abstract, provider value, or secret.

The shared command reporter forwards generic progress only once for each
stage/count. Later same-count receipt substeps update the heartbeat phase but do
not reacquire the formatter lock. This reduces observer overhead; it does not
skip validation, hashes, receipts, or archive files.

Direct `doctor --progress-detail verbose` and explicit private Doctor progress
logs remain detailed and unchanged. Full Doctor can still take minutes on a
large archive; the new phase is liveness evidence, not a completion guarantee.

## v0.3.222 Fast AI Start-Here

v0.3.222 adds no archive migration and writes no archive state. The ordinary
start command is now the fast entry map:

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
```

It reads bounded identity/policy/operational-context metadata and entrypoint
presence. It does not run the complete Doctor, walk every zet, validate every
receipt, or read objet bytes. Check `inspection.mode: quick` and
`inspection.doctor_summary.checked: false`; this is an entry map, not an archive
health claim.

Run the complete archive inspection only when needed:

```text
archive ai-start-here <archive-root> --dry-run --full-doctor --progress --format json
```

Full mode preserves the prior health-check behavior. Doctor can read zet bodies,
local objet bytes, and archive text for secret-pattern checks. The result records
which of those reads actually occurred in this execution. It still accesses no
credential store or provider and writes nothing unless the operator separately
requests a private scratch `--output` file.

Progress now names its unit (`mint_receipts` for the receipt stage), includes
stage elapsed time, rate, and ETA, and carries the latest count in heartbeats.
Compact output suppresses the same stage/count for 30 seconds, so substeps can
no longer flood the terminal with repeated `1/N` lines.

## v0.3.221 Archive-Wide Abstract Receipt Audit

v0.3.221 adds no archive migration and writes nothing. After applying or
reverting abstract batches, run one bounded archive-wide audit:

```text
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

The command verifies each applied receipt in one of two closed states:

```text
applied receipt + current applied hashes
applied receipt + valid revert receipt + current reverted hashes
```

Malformed or orphan receipts and any canonical divergence block. Healthy
lifecycles are returned as counts plus one `audit_digest`; only bounded problem
records are listed. Problem records use hashes and sorted indexes rather than
private paths, ids, bodies, abstracts, or reviewer values.

Recognized locks under `.wom-scratch/abstract-backfill/` are checked without
reading their content:

- matching completed receipt exists: `attention_required` warning; inspect and
  remove manually only after confirming no process is running;
- matching completed receipt is absent: unresolved transaction blocker; inspect
  receipts and canonical hashes before any cleanup.

The audit never deletes locks, edits receipts, repairs canonical zets, calls a
provider/model, or reads a secret store. A green result is local consistency
evidence, not proof of semantic abstract quality or forced-termination safety.

## v0.3.220 Receipt-Audited Abstract Backfill Revert

v0.3.220 adds no archive migration. It adds a receipt-first audit and
approval-gated inverse for a successful v0.3.219 abstract batch. The original
private proposal is not required; retain the applied writer's receipt path and
`receipt.sha256`.

First audit exact reversibility without writing:

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --dry-run --progress --format json
```

`ready_to_revert` means every current canonical file still matches the receipt's
applied after-hash and removing exactly the deterministic inserted `abstract:`
line reconstructs the recorded before-hash. It does not authorize removal.

After a human reviews removal of every recorded abstract, approve the same
receipt explicitly:

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --approve --reviewed-by person:<reviewer> --affirm-abstract-removal-reviewed --progress --format json
```

The revert restores the exact pre-backfill file bytes, preserves the applied
source receipt, and writes one immutable text-free receipt under
`receipts/revisions/abstract-backfill-reverts/`. Any later canonical edit,
abstract change, body change, receipt mismatch, or non-deterministic line shape
blocks the entire batch. An item or revert-receipt runtime failure restores the
applied state.

A matching re-run returns `already_reverted` without writing. To add the same
abstract again later, prepare and review a new proposal byte sequence so it has
a new proposal SHA-256 and a new receipt identity; the old applied receipt stays
closed by its revert receipt.

The short-lived lock is under `.wom-scratch/abstract-backfill/` and does not lock
external editors. Forced termination still has no crash-recovery journal. Do
not delete a leftover lock blindly; inspect both receipts and current hashes.

## v0.3.219 Approval-Gated Abstract Backfill Write

v0.3.219 adds no archive migration. It adds a separate writer for private
proposal files that already passed `zet-abstract-backfill-plan` and human
review. A green plan never writes by itself.

First preview the exact proposal SHA-256 that will be used:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --dry-run --progress --format json
```

Check that the result is `ready_to_apply`. Then a human must review every
abstract in the private proposal. Only after that review, approve the same
bytes explicitly:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --approve --reviewed-by person:<reviewer> --affirm-abstracts-reviewed --progress --format json
```

The command re-runs the plan and rechecks every canonical file hash immediately
before writing. It adds only `frontmatter.abstract`, preserves the original BOM,
newline style, body bytes, and all other parsed frontmatter meaning, then writes
one receipt under `receipts/revisions/abstract-backfill/`. The receipt keeps
target ids and paths plus before/after/body/abstract hashes, but stores no body
or abstract text. Public command output echoes none of those private values or
the reviewer value.

If any item or receipt write raises an error, every attempted canonical file is
restored from its exact in-memory bytes and the incomplete receipt is removed.
One file is capped at 16 MiB and one batch at 256 MiB so rollback snapshots stay
bounded. A matching successful re-run returns `already_applied` without writing.

Do not edit the same target zets concurrently. Runtime errors are rolled back,
but forced process termination, power loss, or machine failure can bypass
in-process cleanup because v0.3.219 writes no crash-recovery journal.

## v0.3.218 Reviewed Abstract Backfill Planning

v0.3.218 adds no archive migration and writes no zet. When a validated catalog
page reports `abstract_status: missing`, read only that selected canonical zet:

```text
archive read-zettel <archive-root> --zettel-id <verified-zet-id> --section body --format json
```

Keep `integrity.file_sha256` with the body-derived candidate. Prepare one
private JSON object per line under `.wom-scratch/abstract-backfill/` using the
shipped `zet-abstract-backfill-proposal.schema.json` contract, then run:

```text
archive zet-abstract-backfill-plan <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --max-items 500 --dry-run --progress --format json
```

The planner checks exact current file bytes, canonical identity/status, missing
first-read state, bounded safe text, and a byte-preserving insertion that adds
only `abstract`. It returns row indexes, counts, and hashes but no ids, paths,
bodies, abstracts, or proposal filename.

Green means `ready_for_human_review`, not approved or applied. v0.3.218 has no
write command. Do not bulk hand-edit canonical files; the transactional,
receipt-backed revision writer is a separate next capability.

## v0.3.217 SHA-Bound Catalog Artifact Lifecycle

v0.3.217 adds no archive migration and does not rewrite a zet. A successful
`zet-catalog-pass` summary now includes `output.sha256`. Keep that value beside
the private scratch filename for the current host session.

Validate the complete artifact without returning private items:

```text
archive zet-catalog-pass-read <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <sha256-from-pass-summary> --dry-run --progress
```

Then request one bounded page at a time with the same hash:

```text
archive zet-catalog-pass-read <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --page-index 0 --expected-sha256 <sha256-from-pass-summary> --dry-run --progress
```

The reader streams and validates the whole JSONL before it returns the selected
page. A malformed footer, broken page chain, changed snapshot, unsupported
field, body-read claim, missing page hash pin, or SHA mismatch returns no page.

After the final `selection.next_page_index` becomes `null`, preview cleanup:

```text
archive zet-catalog-pass-cleanup <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <sha256-from-pass-summary> --dry-run
```

Delete only after human review:

```text
archive zet-catalog-pass-cleanup <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <sha256-from-pass-summary> --approve --reviewed-by human:local-operator
```

Cleanup writes no receipt and never removes hidden partials. The artifact is
disposable private scratch, not WOM knowledge or backup.

## v0.3.216 One-Process Catalog Pass

v0.3.216 adds no archive migration and does not rewrite a zet. For a terminal
AI that must enumerate a large archive, prefer one bounded command instead of
starting a new CLI process for every page:

```text
archive zet-catalog-pass <archive-root> --status canonical --projection reading --page-size 200 --max-estimated-tokens 8000 --response-envelope-reserve-tokens 2500 --max-output-mib 256 --output .wom-scratch/diagnostics/catalog-pass.jsonl --dry-run --progress --format json
```

The first page performs the live frontmatter scan. Intermediate pages reuse
only memory owned by that process. Before a multi-page pass can finish, the
command rechecks the selected local file state; a changed snapshot blocks and
the complete output path is not created.

The JSONL contains one header, one record per strict page, and one completion
footer. It may contain private zet ids, titles, abstracts, facets, ties, and
edges. It contains no zet body text, is not an archive record or receipt, must
not be committed, and should be read incrementally and deleted after use.

The destination must be a new `.jsonl` path below
`.wom-scratch/diagnostics/`. Existing files are never overwritten. Normal
failures remove the new hidden partial. A forced process termination can leave
a hidden private partial; later runs report only its count and neither read nor
delete it automatically. Confirm that no pass is running before manual cleanup.

Ordinary paged `zet-catalog` and MCP behavior remain compatible. The new
command persists no cache, generated map, index, host goal, or loop state and
calls no provider.

## v0.3.215 Project Version Update

v0.3.215 adds the first approval-gated source-mirror and version-pin updater.
It does not migrate or rewrite archive zets.

Preview without network or writes:

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --progress --format json
```

After reviewing a clean preview, approve one transaction:

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --approve --reviewed-by <actor> --affirm-external-writers-quiescent --progress --format json
```

On the current CLI, first pause editors, sync/backup clients, and other Git
writers for the complete transaction; the affirmation flag above is required
for every approval. The original v0.3.215 boundary fetched only configured
`origin/main` and the exact target tag, required an annotated tag on that main
history, verified all three package version files, aligned recognized pins, and
wrote a project metadata receipt. The current v0.3.291 updater still keeps that
bounded fetch but manually materializes the complete target commit tree without
`git checkout`. Rollback now uses checkpointed drift detection and may remain
incomplete with the owned lock preserved; the v0.3.291 section above is the
current operational contract. Fetched refs may remain as non-canonical
discovery state.

The current Python process is never reloaded. After success, start a new process
from the project mirror and run `archive version <root> --format json` before
claiming the target runtime is active. The check verifies configured-origin
provenance but not a cryptographic tag signature.

Bootstrap limit: installations older than v0.3.215 do not contain this command.
They need one final existing/manual verified update to v0.3.215; use the command
for later releases.

## v0.3.214 Large-Command Progress And Bounded Output

v0.3.214 adds no migration and rewrites no zet. Long `ai-start-here`,
`upgrade-check`, and CLI `zet-catalog` runs can opt into content-free liveness:

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
archive upgrade-check <archive-root> --dry-run --progress --format json
archive zet-catalog <archive-root> --coverage-mode strict --cursor 0 --dry-run --progress --format json
```

Progress goes only to stderr. The final result remains on stdout. Optional
`--output .wom-scratch/diagnostics/<name>.json` stores the full JSON result and
prints only a compact stdout summary. It creates a private scratch file, not an
archive record or receipt; it refuses overwrite and should not be committed.

Catalog progress makes each live scan visible but does not persist a cache or
remove the full scan performed by a new CLI process. Existing archives and
callers that omit both options behave as before.

## v0.3.213 Local Sovereignty Authority

v0.3.213 adds no migration and rewrites no zet. It adds a read-only
`local-sovereignty` contract and exposes the same `storage_authority` model in
runtime, start-here, recovery, and upgrade-check output.

Local reviewed WOM state is canonical. GitHub, object storage, and external
databases are backup/replica layers. Existing provider bindings are not changed
and the command performs no live backup audit. `ai-start-here` schema advances
to v0.2; callers that validate that result schema should accept the new field
and version.

## v0.3.212 Compact Strict Continuations

v0.3.212 adds optional `--response-profile continuation` after the first page
of a strict catalog pass. Cursor zero must remain `full`; retain its scope-wide
abstract, identity, order, scan, and workload diagnostics. Later compact pages
keep items, readiness, snapshot, token, chain, session, warning, and privacy
fields while omitting repeated diagnostics.

Catalog schema advances to v0.8. Continuation schema remains v0.3 because the
response profile does not change item selection, order, cursor, or chain
identity. Existing callers remain full by default, and in-flight v0.3.211
strict passes may opt into compact responses on their next nonzero cursor.
Existing archives require no migration and no zet is rewritten.

## v0.3.211 Response Envelope Budget

v0.3.211 adds response-size measurement and optional
`--response-envelope-reserve-tokens`. Existing calls keep items-only
`max_estimated_tokens` semantics. When a reserve is provided, WOM subtracts it
from that value and uses the remainder as the effective items budget.

Catalog schema advances to v0.7; continuation schema remains v0.3, so an
in-flight strict pass may change its page size, item budget, or reserve without
restarting. Measurements are heuristic and exclude their own block, CLI pretty
whitespace, and MCP/JSON-RPC framing. Existing archives require no migration.

## v0.3.210 Routed Reading Evidence

v0.3.210 adds `projection=routed_reading` for seeded connection order. Normal
`projection=reading` remains the compact default. Routed reading is valid only
with `order=seeded_connection_walk` and verified start zet ids.

Catalog schema advances to v0.6. Strict continuation schema advances to v0.3
because chain hashes now distinguish snapshot file entries instead of relying
only on zet ids. Restart any v0.3.209 in-flight strict pass at cursor zero.
Tokens remain transient, checksum-based drift guards rather than signatures or
receipts. Existing archives require no migration and no zet is rewritten.

## v0.3.209 First-Read Readiness Signals

v0.3.209 adds no migration and does not rewrite existing zets. Catalog output
schema advances to v0.5 while the strict continuation-token schema remains
v0.2.

After a strict pass, interpret the three signals separately:

- `archive_wide_coverage_claim_ready`: every selected file node was visited;
- `archive_wide_abstract_reading_claim_ready`: every non-redacted node also
  supplied readable first-read text;
- `archive_wide_followup_resolution_ready`: every node has a readable, safe,
  unique frontmatter id for id-only follow-up.

A false abstract or follow-up signal is a review gap, not an automatic repair
request. Do not generate missing abstracts or rewrite ids without human review.

## v0.3.208 Seeded Exhaustive Reading Order

v0.3.208 adds optional `--order seeded_connection_walk` and repeated
`--start-zettel-id` (MCP: `order`, `start_zettel_ids`). Existing path order
remains the default and archives require no migration.

Use seeds only when the host goal or human already provides verified zet ids.
The command blocks missing seeds instead of guessing. Seed-connected nodes come
first, then every disconnected component follows, so this changes order but
never narrows coverage.

Continuation-token schema advances to v0.2 to bind the seed-list fingerprint.
Restart any v0.3.207 in-flight strict pass at cursor 0 after upgrading; tokens
are transient and are not archive records.

## v0.3.207 Compact Reading And Strict Coverage

v0.3.207 adds optional `projection=reading` and `coverage_mode=strict` to CLI
and MCP catalog calls. Existing callers keep `projection=full` and
`coverage_mode=page`; no archive migration is required.

For archive-wide AI reading, start strict mode at cursor 0. Every continuation
must pass the prior page's `coverage.continuation_token`. Only
`archive_wide_coverage_claim_ready: true` proves that this strict chain reached
the end. The older `complete` field still means the requested page reached the
scope end and must not be treated as contiguous-pass proof by itself.

The token is checksum validated and stateless. It is not a signature,
attestation, security credential, or receipt.

## v0.3.206 Catalog Scale And Token Budget

v0.3.206 adds workload estimates and optional `max_estimated_tokens` to CLI and
MCP catalog pages. Existing archives and callers require no migration; omitting
the option preserves item-count pagination.

Token estimates cover catalog item JSON only. They use a transparent
four-characters-per-token heuristic and are not provider-reported usage. MCP
keeps a process-local materialized snapshot for intermediate pages and
revalidates local file metadata before returning the completing page. Restart
at cursor 0 if that check reports `catalog_snapshot_changed`.

## v0.3.205 Host-AI Abstract Reading

v0.3.205 exposes the v0.3.204 live catalog through MCP and adds a `section`
argument to MCP `read_zettel`. Existing clients that omit `section` keep the
previous `body` default. Existing archives require no migration.

Host applications should call `zet_catalog`, follow `next_cursor` with the
same `snapshot.id` until `complete: true`, and request
`read_zettel(section: "overview")` before broader body reads. If the snapshot
changes, restart at cursor 0 rather than mixing archive states.

## v0.3.204 Optional Abstract

v0.3.204 adds optional `frontmatter.abstract` and the read-only live
`zet-catalog`. Existing archives require no migration and no zet is rewritten.

New or revised drafts may add a compact abstract with:

```text
archive create-draft <archive-root> --title <title> --abstract <text> --body <body>
```

Old zets without the field appear as `abstract_status: missing`. Review and
revise them gradually; do not bulk-generate or silently write abstracts only to
make the catalog look complete.

## Public Versions

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.3.208` | current public pre-release | `wom-kit/docs/releases/v0.3.208.md` |
| `v0.3.207` | superseded public pre-release | `wom-kit/docs/releases/v0.3.207.md` |
| `v0.3.206` | superseded public pre-release | `wom-kit/docs/releases/v0.3.206.md` |
| `v0.3.205` | superseded public pre-release | `wom-kit/docs/releases/v0.3.205.md` |
| `v0.3.204` | superseded public pre-release | `wom-kit/docs/releases/v0.3.204.md` |
| `v0.3.203` | superseded public pre-release | `wom-kit/docs/releases/v0.3.203.md` |
| `v0.3.202` | superseded public pre-release | `wom-kit/docs/releases/v0.3.202.md` |
| `v0.3.201` | superseded public pre-release | `wom-kit/docs/releases/v0.3.201.md` |
| `v0.3.200` | superseded public pre-release | `wom-kit/docs/releases/v0.3.200.md` |
| `v0.3.199` | superseded public pre-release | `wom-kit/docs/releases/v0.3.199.md` |
| `v0.3.198` | superseded public pre-release | `wom-kit/docs/releases/v0.3.198.md` |
| `v0.3.197` | superseded public pre-release | `wom-kit/docs/releases/v0.3.197.md` |
| `v0.3.196` | superseded public pre-release | `wom-kit/docs/releases/v0.3.196.md` |
| `v0.3.195` | superseded public pre-release | `wom-kit/docs/releases/v0.3.195.md` |
| `v0.3.194` | superseded public pre-release | `wom-kit/docs/releases/v0.3.194.md` |
| `v0.3.193` | superseded public pre-release | `wom-kit/docs/releases/v0.3.193.md` |
| `v0.3.192` | superseded public pre-release | `wom-kit/docs/releases/v0.3.192.md` |
| `v0.3.191` | superseded public pre-release | `wom-kit/docs/releases/v0.3.191.md` |
| `v0.3.190` | superseded public pre-release | `wom-kit/docs/releases/v0.3.190.md` |
| `v0.3.189` | superseded public pre-release | `wom-kit/docs/releases/v0.3.189.md` |
| `v0.3.188` | superseded public pre-release | `wom-kit/docs/releases/v0.3.188.md` |
| `v0.3.187` | superseded public pre-release | `wom-kit/docs/releases/v0.3.187.md` |
| `v0.3.186` | superseded public pre-release | `wom-kit/docs/releases/v0.3.186.md` |
| `v0.3.7` | superseded public pre-release | `wom-kit/docs/releases/v0.3.7.md` |
| `v0.3.6` | superseded public pre-release | `wom-kit/docs/releases/v0.3.6.md` |
| `v0.3.5` | superseded public pre-release | `wom-kit/docs/releases/v0.3.5.md` |
| `v0.3.4` | superseded public pre-release | `wom-kit/docs/releases/v0.3.4.md` |
| `v0.3.3` | superseded public pre-release | `wom-kit/docs/releases/v0.3.3.md` |
| `v0.3.2` | superseded public pre-release | `wom-kit/docs/releases/v0.3.2.md` |
| `v0.3.1` | superseded public pre-release | `wom-kit/docs/releases/v0.3.1.md` |
| `v0.3.0` | superseded public pre-release | `wom-kit/docs/releases/v0.3.0.md` |
| `v0.2.60` | superseded public pre-release | `wom-kit/docs/releases/v0.2.60.md` |
| `v0.2.59` | superseded public pre-release | `wom-kit/docs/releases/v0.2.59.md` |
| `v0.2.58` | superseded public pre-release | `wom-kit/docs/releases/v0.2.58.md` |
| `v0.2.57` | superseded public pre-release | `wom-kit/docs/releases/v0.2.57.md` |
| `v0.2.56` | superseded public pre-release | `wom-kit/docs/releases/v0.2.56.md` |
| `v0.2.55` | superseded public pre-release | `wom-kit/docs/releases/v0.2.55.md` |
| `v0.2.54` | superseded public pre-release | `wom-kit/docs/releases/v0.2.54.md` |
| `v0.2.53` | superseded public pre-release | `wom-kit/docs/releases/v0.2.53.md` |
| `v0.2.52` | superseded public pre-release | `wom-kit/docs/releases/v0.2.52.md` |
| `v0.2.51` | superseded public pre-release | `wom-kit/docs/releases/v0.2.51.md` |
| `v0.2.50` | superseded public pre-release | `wom-kit/docs/releases/v0.2.50.md` |
| `v0.2.49` | superseded public pre-release | `wom-kit/docs/releases/v0.2.49.md` |
| `v0.2.48` | superseded public pre-release | `wom-kit/docs/releases/v0.2.48.md` |
| `v0.2.47` | superseded public pre-release | `wom-kit/docs/releases/v0.2.47.md` |
| `v0.2.46` | superseded public pre-release | `wom-kit/docs/releases/v0.2.46.md` |
| `v0.2.45` | superseded public pre-release | `wom-kit/docs/releases/v0.2.45.md` |
| `v0.2.44` | superseded public pre-release | `wom-kit/docs/releases/v0.2.44.md` |
| `v0.2.43` | superseded public pre-release | `wom-kit/docs/releases/v0.2.43.md` |
| `v0.2.42` | superseded public pre-release | `wom-kit/docs/releases/v0.2.42.md` |
| `v0.2.41` | superseded public pre-release | `wom-kit/docs/releases/v0.2.41.md` |
| `v0.2.40` | superseded public pre-release | `wom-kit/docs/releases/v0.2.40.md` |
| `v0.2.39` | superseded public pre-release | `wom-kit/docs/releases/v0.2.39.md` |
| `v0.2.38` | superseded public pre-release | `wom-kit/docs/releases/v0.2.38.md` |
| `v0.2.37` | superseded public pre-release | `wom-kit/docs/releases/v0.2.37.md` |
| `v0.2.36` | superseded public pre-release | `wom-kit/docs/releases/v0.2.36.md` |
| `v0.2.35` | superseded public pre-release | `wom-kit/docs/releases/v0.2.35.md` |
| `v0.2.34` | superseded public pre-release | `wom-kit/docs/releases/v0.2.34.md` |
| `v0.2.33` | superseded public pre-release | `wom-kit/docs/releases/v0.2.33.md` |
| `v0.2.32` | superseded public pre-release | `wom-kit/docs/releases/v0.2.32.md` |
| `v0.2.31` | superseded public pre-release | `wom-kit/docs/releases/v0.2.31.md` |
| `v0.2.30` | superseded public pre-release | `wom-kit/docs/releases/v0.2.30.md` |
| `v0.2.29` | superseded public pre-release | `wom-kit/docs/releases/v0.2.29.md` |
| `v0.2.28` | superseded public pre-release | `wom-kit/docs/releases/v0.2.28.md` |
| `v0.2.27` | superseded public pre-release | `wom-kit/docs/releases/v0.2.27.md` |
| `v0.2.26` | superseded public pre-release | `wom-kit/docs/releases/v0.2.26.md` |
| `v0.2.25` | superseded public pre-release | `wom-kit/docs/releases/v0.2.25.md` |
| `v0.2.24` | superseded public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
| `v0.2.23` | superseded public pre-release | `wom-kit/docs/releases/v0.2.23.md` |
| `v0.2.22` | superseded public pre-release | `wom-kit/docs/releases/v0.2.22.md` |
| `v0.2.21` | superseded public pre-release | `wom-kit/docs/releases/v0.2.21.md` |
| `v0.2.20` | superseded public pre-release | `wom-kit/docs/releases/v0.2.20.md` |
| `v0.2.19` | superseded public pre-release | `wom-kit/docs/releases/v0.2.19.md` |
| `v0.2.18` | superseded public pre-release | `wom-kit/docs/releases/v0.2.18.md` |
| `v0.2.17` | superseded public pre-release | `wom-kit/docs/releases/v0.2.17.md` |
| `v0.2.16` | superseded public pre-release | `wom-kit/docs/releases/v0.2.16.md` |
| `v0.2.15` | superseded public pre-release | `wom-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `wom-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `wom-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `wom-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `wom-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `wom-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `wom-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `wom-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `wom-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `wom-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `wom-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `wom-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `wom-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `wom-kit/docs/releases/v0.2.2.md` |

## From `v0.3.202` To `v0.3.203`

One additive user-reviewed operator vocabulary correction. No migration is required.

Operator-visible notes:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json` now reports the reviewed operator
  vocabulary under `confirmed_operator_language`.
- The reviewed Korean operator terms include `object_id` as `오브제 아이디`,
  `doctor` as `검진`, `provider` as `외부 서비스`, `containment` as `포함 관계`,
  `safe_preview` as `미리보기`, `approved_write` as `승인 후 쓰기`,
  `external_report` as `공개용 문서`, and `private_working_note` as
  `비공개 문서`.
- `needs_user_translation` remains available as an empty bucket for future
  naming-review items.
- See `wom-kit/docs/releases/v0.3.203.md`.

## From `v0.3.201` To `v0.3.202`

One additive read-only Korean-first vocabulary patch for AI operators. No migration is required.

Operator-visible notes:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json` now returns a grouped vocabulary
  layer for archive entrypoints, zets/drafts, objets/evidence, lifecycle
  actions, checks, connections, providers, and secrets.
- The `all` topic includes the new `operator_vocabulary` section.
- Machine terms stay unchanged; the new phrases guide human-facing prose only.
- See `wom-kit/docs/releases/v0.3.202.md`.

## From `v0.3.200` To `v0.3.201`

One additive read-only AI operator signpost. No migration is required.

Operator-visible notes:

- New `archive ai-start-here <archive-root> --dry-run --format markdown|json`
  command, with `start-here` and `operator-start-here` aliases.
- The command projects existing runtime-context, canonical entrypoint, and
  operational-context metadata into one first-read map for an entering AI
  operator.
- It writes nothing, calls no providers, reads no secrets, reads no zettel
  bodies or objet bytes, and redacts local absolute paths by default.
- See `wom-kit/docs/releases/v0.3.201.md`.

## From `v0.3.199` To `v0.3.200`

One additive schema/doctor validation patch for object-storage manifest reconcile audit receipts. No migration is required.

Operator-visible notes:

- `object-storage-wom-location-reconcile --approve` still writes the same
  local-only audit receipt, but that receipt now has a public JSON schema:
  `wom-kit/schemas/object-storage-manifest-reconcile-receipt.schema.json`.
- `archive doctor` now checks object-storage manifest reconcile audit receipts
  for schema, action, reviewer, path, updated execution receipt refs, positive
  update counts, and non-echo privacy guards.
- The command behavior, approval gates, and no-provider/no-credential/no-object-byte
  boundaries are unchanged.
- See `wom-kit/docs/releases/v0.3.200.md`.

## From `v0.3.198` To `v0.3.199`

One additive object-storage receipt/manifest binding repair patch. No migration is required.

Operator-visible notes:

- `archive doctor` no longer flags a repeated `skipped_remote_same` receipt as
  `object_storage_upload_wom_location_missing` when an existing valid
  `wom_uploaded` location already covers the same object/provider/store/remote
  key.
- New CLI command:
  `archive object-storage-wom-location-reconcile <archive-root> --receipt
  <receipt> --dry-run|--approve`.
- Always run `--dry-run` first. `--approve` requires `--reviewed-by`.
- The command never calls providers, reads credentials, reads object bytes,
  uploads, downloads, syncs, or checks remote availability.
- Approved mode writes only `objects/manifests/files.jsonl` plus one audit
  receipt under `receipts/providers/object-storage-manifest-reconciles/`.
- Candidate output intentionally does not echo object ids, remote keys, bucket
  names, provider URLs, exact credential refs, or local absolute paths.
- See `wom-kit/docs/releases/v0.3.199.md`.

## From `v0.3.197` To `v0.3.198`

One additive reconcile approval-result status cleanup patch. No migration is required.

Operator-visible notes:

- `remint-reconcile --approve --format json` and
  `retire-draft-reconcile --approve --format json` now report
  `status: reconcile_applied` and `overall_status: reconcile_applied` after a
  successful write.
- The approval result now points to `suggested_next_action:
  run_doctor_to_verify_reconcile` and doctor verification `next_safe_actions`.
- Applied approval output no longer keeps the earlier dry-run
  `needs_content_change_review` status, and no longer says a new approval write
  is pending.
- On Windows, prefer explicit UTF-8 capture for JSON examples instead of bare
  PowerShell `>` redirection.
- When directly repairing a schema enum on a zettel that also has retired-draft
  receipts, use the paired reviewed flow: `remint-reconcile` first, then
  `retire-draft-reconcile`, each dry-run before approve.
- Reconcile classification and approval gates are unchanged.
- See `wom-kit/docs/releases/v0.3.198.md`.

## From `v0.3.196` To `v0.3.197`

One additive reconcile dry-run next-action guidance patch. No migration is required.

Operator-visible notes:

- `remint-reconcile --dry-run --format json` and `retire-draft-reconcile --dry-run --format json`
  now include `status`, `overall_status`, `suggested_next_action`, `would_write`,
  `approval_would_write`, and `approval_requires_content_changed_ack`.
- A `content_change` dry-run now says that human content review is required before any
  `--approve --content-changed-ack` run.
- `retire-draft-reconcile --format text` now prints `Next safe actions` when present.
- Reconcile classification and approval gates are unchanged.
- See `wom-kit/docs/releases/v0.3.197.md`.

## From `v0.3.195` To `v0.3.196`

One additive doctor progress-log path-policy clarification patch. No migration is required.

Operator-visible notes:

- `doctor --progress-log <path>` summary output now marks relative progress-log paths as
  cwd-relative and relative to the current working directory.
- The summary labels progress logs as local progress artifacts, not archive receipts, and says
  not to commit them by default.
- Absolute progress-log inputs are not echoed in the summary.
- Default `doctor` behavior, progress-log write behavior, and exit-code semantics are unchanged.
- See `wom-kit/docs/releases/v0.3.196.md`.

## From `v0.3.194` To `v0.3.195`

One additive doctor output path-policy clarification patch. No migration is required.

Operator-visible notes:

- `doctor --output <path>` summary output now marks the path as archive-relative and relative to
  the archive root.
- The summary labels full doctor result files as local diagnostic artifacts, not archive receipts,
  and says not to commit them by default.
- `mint_retired_draft_sha_mismatch` now includes a hint explaining why
  `retire-draft-reconcile --dry-run` is the safe first step.
- Default `doctor` behavior and exit-code semantics are unchanged.
- See `wom-kit/docs/releases/v0.3.195.md`.

## From `v0.3.193` To `v0.3.194`

One additive doctor result-capture and diagnostic-guidance patch. No migration is required.

Operator-visible notes:

- `doctor --output <path>` writes the full diagnostics JSON array to a file and prints a compact
  stdout summary.
- `doctor --summary`, `--errors-only`, and `--diagnostic-level ERROR,WARN` reduce stdout volume
  without changing exit-code semantics.
- `provenance.creation_mode` enum errors, object-storage receipt/manifest link gaps, and BOM
  zettel warnings now include safer next-action hints.
- Default `doctor` output is unchanged unless the new options are used.
- See `wom-kit/docs/releases/v0.3.194.md`.

## From `v0.3.192` To `v0.3.193`

One additive doctor local-profile secret-safety progress patch. No migration is required.

Operator-visible notes:

- `doctor --progress` now emits internal progress for `local-profile-secret-safety`: gitignore
  checks, archive walking, checked-file counts, content-scan counts, local-profile counts,
  skipped-dir counts, and a final summary.
- Large archive walks can emit `still checking local profile secret safety` heartbeats.
- Eligible config/text secret-content checks now stream in chunks and can emit
  `still scanning secret content ...` for long reads.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged except for any
  pre-existing diagnostics the stage already reported.
- See `wom-kit/docs/releases/v0.3.193.md`.

## From `v0.3.191` To `v0.3.192`

One additive doctor progress volume-control patch. No migration is required.

Operator-visible notes:

- `doctor --progress` now uses compact stderr progress by default, keeping stage start/done,
  receipt milestones, quiet-interval heartbeats, and key edge-index lifecycle events.
- Use `doctor --progress --progress-detail verbose` to preserve the full detailed receipt trace.
- Use `doctor --progress-log <path>` to write every progress event as JSONL while stderr remains
  compact; the log option can also be used without `--progress`.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.192.md`.

## From `v0.3.190` To `v0.3.191`

One additive doctor edge-evolution progress patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now names the target edge-receipt evolution target with an
  archive-relative path after a mint target sha mismatch.
- Edge receipt index work now reports loading, scan counts, ready counts, cache hits, and target
  candidate counts.
- Target evolution replay now reports target zettel reads, missing-cutoff/no-edge-list skips,
  strict/inclusive history checks, and ok/no-match results.
- Long edge receipt scans can emit `still scanning edge receipts` liveness.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.191.md`.

## From `v0.3.189` To `v0.3.190`

One additive doctor file-ref drilldown patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now drills into mint receipt file-reference checks: resolving path,
  checking existence, resolved archive-relative ref, sha field check, stat, cache hit, hash
  start/end, mismatch, target edge-evolution check, and ref-ok.
- Fresh SHA-256 reads now always emit `hashing <section> file bytes` before reading, regardless of
  file size.
- `still hashing ... file bytes` remains a chunk heartbeat for longer reads, not a mandatory
  small-file line.
- Retired mint sources now emit `source file ref skipped; source retired`.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.190.md`.

## From `v0.3.188` To `v0.3.189`

One additive doctor liveness patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now emits `started receipt checks`, source/target/snapshot file-ref
  check names, and `completed receipt checks` for every mint receipt.
- Large mint-receipt file SHA checks can emit content-free `hashing ... file bytes`,
  `still hashing ... file bytes`, and `hashed ... file bytes` liveness.
- The heartbeat-mode transition message now says minimal file-ref liveness is emitted every receipt.
- Counted-stage ETA stays `eta=warming_up` through the first nine samples or first 30 seconds of a
  stage.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.189.md`.

## From `v0.3.187` To `v0.3.188`

One additive doctor progress patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now emits a mint-receipt entry for every checked mint receipt.
- Detailed mint-receipt sub-steps now run through receipt 4, then resume every 250 receipts and
  for the final receipt.
- After receipt 4, progress explicitly says it is continuing with receipt heartbeat and sampled
  detailed substeps.
- Counted-stage ETA uses per-stage timing and reports `eta=warming_up` for the first few samples
  instead of projecting from too little data.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.188.md`.

## From `v0.3.186` To `v0.3.187`

One additive AI artifact lifecycle inventory patch. No migration is required.

Operator-visible notes:

- `archive ai-artifact-inventory <archive-root> --dry-run --format json` inventories AI-generated
  artifact candidates under allowlisted roots only: `.wom-scratch/`, `workbench/ai-scratch/`,
  `staging/ai/inbox/`, and `staging/ai/reviewed/`.
- The inventory reports whether candidates are still `unreviewed_ai_artifact` or already have a
  matching AI artifact `source-intake-record`.
- JSONL chat logs and other AI-generated files are treated as possible raw evidence to preserve as
  objets, not as canonical zet bodies. The safe path is raw artifact -> objet/source evidence ->
  derived/distilled text -> draft zet -> human review -> canonical zet.
- The command reads no file bodies, calculates no content hashes, writes nothing, deletes nothing,
  creates no zets, calls no providers, and hides archive-relative paths unless
  `--show-relative-paths` is explicitly used for local operator review.
- See `wom-kit/docs/releases/v0.3.187.md`.

## From `v0.3.185` To `v0.3.186`

One additive operator-diagnostics patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing` now accepts `--stop-after-plan`. It may be combined with an
  `--approve` command shape to resolve the same key-map/resume plan, then stop before credential
  value reads, provider HEADs, manifest updates, or execution receipt writes.
- The final `--format json` or text result is written to stdout. Optional `--progress` heartbeats
  are written to stderr, so scripts that need the structured result should watch stdout or redirect
  stderr separately.
- `adopt_summary` now includes `plan_only`, `plan_only_stop_stage`,
  `planned_remote_head_count`, `unresolved_remote_key_count`,
  `existing_matching_wom_uploaded_location_count`, and same-store `wom_uploaded`
  raw-vs-gating counts. These explain why a simple `store_ref` manifest count can be higher than
  the stricter resume skip candidates.
- `doctor --strict --progress` now emits detailed mint-receipt sub-steps for the first three
  receipts and prints `completed receipt checks` for detailed receipts, making a post-link stall
  easier to localize.
- See `wom-kit/docs/releases/v0.3.186.md`.

## From `v0.3.184` To `v0.3.185`

One additive diagnostics patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing --progress` still prints the v0.3.183 matching resume summary.
  It now also prints a `resume nonmatching-provider summary` when same-provider digest-bound
  locations exist but do not match this run's `store_ref` or resolved `remote_key`.
- `adopt_summary` now includes `same_provider_nonmatching_location_count`,
  `same_provider_nonmatching_declared_uploaded_count`, `same_provider_store_ref_mismatch_count`,
  and `same_provider_remote_key_mismatch_count`.
- `provider_location_mismatch_gap` warns that legacy/nonmatching `declared_uploaded` locations are
  evidence, but not `--skip-existing-wom-uploaded` candidates for the current store/key run.
- `doctor --strict --progress` now splits `checking target mint receipt link` into target mint block,
  receipt-path, relative-path, comparison, and ok/error sub-steps.
- `archive version <root>` text output now includes an import-module redaction line, and
  `--no-redact-local-paths` can show the active module path when diagnosing source-mirror/editor
  install drift.
- See `wom-kit/docs/releases/v0.3.185.md`.

## From `v0.3.183` To `v0.3.184`

One additive human-readable zet viewer patch. No migration is required.

Operator-visible notes:

- `archive read-zettel --section document` now gives a WOM-rendered document read of one zet:
  frontmatter details are hidden and text output prints only the body.
- JSON output includes `viewer_mode`, `frontmatter_hidden`, and
  `raw_frontmatter_delimiters_echoed: false` so simple viewers can separate storage metadata from
  document content.
- The canonical Markdown file format still uses YAML frontmatter for ids, provenance, edges,
  visibility, and receipts. The change is about the reading surface, not the storage format.
- See `wom-kit/docs/zet-frontmatter-viewer-contract.md` and
  `wom-kit/docs/releases/v0.3.184.md`.

## From `v0.3.182` To `v0.3.183`

One additive resume-diagnostics and progress patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing --progress` now prints an `adopt-plan` resume summary with
  matching provider/store/key location counts split into `wom_uploaded`, `declared_uploaded`, and
  other. This appears before the verified remote-HEAD loop.
- `adopt_summary` now includes `existing_matching_location_count`,
  `existing_declared_uploaded_count`, `existing_other_location_count`, and
  `expected_resume_skip_count`.
- Matching `declared_uploaded` locations now emit `declared_upload_resume_gap`: they explain a
  partial state where many provider/store/key locations exist but cannot be skipped by
  `--skip-existing-wom-uploaded` because they are not WOM-verified `wom_uploaded` locations.
- `doctor --strict --progress` now breaks target frontmatter loading into read/BOM/fence/YAML/load
  and mint-link sub-steps.
- See `wom-kit/docs/releases/v0.3.183.md`.

## From `v0.3.181` To `v0.3.182`

One additive protected-pilot revalidation follow-up. No migration is required.

Operator-visible notes:

- `archive object-storage-adopt-existing ... --approve --skip-existing-wom-uploaded` is a
  resume helper for interrupted verified adopts. Objects that already have a matching
  `wom_uploaded` manifest location for the same provider/store/key are reported as
  `already_wom_uploaded_manifest` and are not remote-HEADed again.
- The default remains conservative: without `--skip-existing-wom-uploaded`, verified adopt still
  re-HEADs each resolved key. The resume option is refused with `--content-hash-verify`.
- Adopt planning now reports how many matching existing `wom_uploaded` locations it found and
  emits a `resume_hint` warning when the count is nonzero but the resume option is not enabled.
- `archive doctor --strict --progress` now prints sampled `mint-receipts` sub-steps and a cache
  summary for file SHA-256, zettel frontmatter, and BOM evidence.
- See `wom-kit/docs/releases/v0.3.182.md`.

## From `v0.3.180` To `v0.3.181`

One additive operator-progress patch. No migration is required.

Operator-visible notes:

- `archive staged-cleanup-check <root> --staged <folder> --dry-run --progress` now streams
  content-free progress to stderr while it loads manifests, scans zettel references, walks staged
  entries, verifies files, and hashes large staged/store files.
- Default command output and result JSON are unchanged when `--progress` is omitted.
- Progress lines include stage names and counts/byte totals only. They do not add staged file
  names, object ids, local absolute paths, provider URLs, tokens, or secret values.
- See `wom-kit/docs/releases/v0.3.181.md`.

## From `v0.3.179` To `v0.3.180`

One additive performance-hardening patch. No migration is required.

Operator-visible notes:

- **Large `object-storage-adopt-existing --key-map` plan resolution should no longer scan the
  manifest once per object.** The adopt plan now builds one per-run manifest index and uses
  O(1) object-id lookup while preserving first-record-wins semantics.
- **`archive doctor` receipt stages reuse per-run file evidence.** File SHA-256 and zettel
  frontmatter/BOM checks are cached during one doctor run, reducing repeated disk reads in
  `mint-receipts` and related receipt checks.
- Existing command shapes, progress output, result JSON, and receipt formats are unchanged.
- See `wom-kit/docs/releases/v0.3.180.md`.

## From `v0.3.178` To `v0.3.179`

One additive redacted diagnostic-output patch. No migration is required.

Operator-visible notes:

- **`archive remint-reconcile --diagnostic-only --format json`** is a dry-run-only projection
  that keeps `drift_class`, `body_changed`, `body_diff_diagnostic`, blockers/warnings, and
  frontmatter field names/counts while omitting `current_canonical_text` and frontmatter values.
- **Approval is intentionally not redacted.** `--diagnostic-only` is refused with `--approve`
  because the approve path must still show the current on-disk content for human review.
- Existing `remint-reconcile --format json` output is unchanged for compatibility.
- See `wom-kit/docs/releases/v0.3.179.md`.

## From `v0.3.177` To `v0.3.178`

One additive operator-progress patch. No migration is required.

Operator-visible notes:

- **`archive doctor --progress`** streams stage start/done lines to stderr during long doctor
  runs. JSON/text diagnostic output is unchanged.
- **`object-storage-adopt-existing --progress`** streams safe stage/count heartbeats for plan
  resolution and adopt HEAD loops. It does not print object ids, remote keys, bucket names,
  provider URLs, exact credential refs, tokens, or secret values.
- **No migration; default output unchanged.** The new output appears only when `--progress` is
  passed.
- See `wom-kit/docs/releases/v0.3.178.md`.

## From `v0.3.176` To `v0.3.177`

One additive force-reupload hardening patch for the object-storage upload adapter. No migration is
required; default idempotency behavior is unchanged.

Operator-visible notes:

- **`--force-reupload` now also bypasses resume-ledger-only skips.** If a post-crash or
  handoff state has a terminal resume-ledger row but the manifest does not currently have a
  `wom_uploaded` location, a reviewed force run now reaches the provider PUT path instead of
  returning `skipped_already_present`.
- **A forced zero-PUT result is blocked.** Force run output includes `forced_reupload: true`;
  if no provider PUT is attempted, the run reports `force_reupload_not_performed` with
  `ok:false` instead of a misleading executed success.
- **No migration; no default behavior change.** Without `--force-reupload`, the existing
  resume-ledger/idempotency skips behave as before.
- See `wom-kit/docs/releases/v0.3.177.md`.

## From `v0.3.175` To `v0.3.176`

One additive, DX-only reconcile body-diff diagnostic. **No behavior or classification change, no
migration.** The drift classifier is byte-identical.

Operator-visible notes:

- **`v0.3.176` adds a content-free `body_diff_diagnostic`** to the `remint-reconcile` and
  `retire-draft-reconcile` plan output. When a drift is classified `content_change` because the
  two bodies still differ AFTER the single leading BOM strip + CRLF/CR→LF fold, the plan now
  reports WHICH kind of sub-BOM residual it is: a fixed `category`
  (`final_newline_only` / `trailing_whitespace_only` / `unicode_normalization_only` /
  `content_difference`), a `first_differing_byte_offset` (an integer), a `normalized_length_delta`
  (an integer), and — for the unicode case only — a closed-enum NFC/NFD form label. It emits ONLY
  numbers and fixed labels, never any body text.
- **It is a STRICT CLASSIFICATION NO-OP.** It is computed AFTER the drift_class predicate and only
  decorates the output dict (exactly like the v0.3.172 strip-BOM preview). `drift_class`,
  `classification_basis`, `content_change_ack_required`, and `bytes_normalized_for_content_compare`
  are byte-identical with and without it. A mixed whitespace/normalization + real-edit diff stays
  the honest `content_difference` — never laundered.
- **The key is absent when it would be misleading**: on a no-anchor / no-snapshot plan
  (`body_changed` None) and on a `format_drift` plan (`body_changed` False). Both CLI text printers
  gain one content-free summary line; JSON consumers see the key only when present.
- **No migration; no behavior change.** Existing receipts and manifests are unaffected.
- See `wom-kit/docs/releases/v0.3.176.md`.

## From `v0.3.174` To `v0.3.175`

Two additive live-verification aids for the object-storage upload adapter. No migration is
required; default behavior and existing receipts/manifests are byte-identical.

Operator-visible notes:

- **`v0.3.175` adds an approval-gated `--force-reupload`** on `object-storage-upload`. It
  re-PUTs an already-present, size/hash-matching object so a client can exercise a LIVE
  provider PUT (e.g. a forced small multipart). It requires `--approve` AND `--reviewed-by`,
  is refused for any non-sha-derived `--key-strategy`, is inert under `--dry-run`, and still
  runs the pre-PUT local `sha256(local)==object_id` re-verify so a corrupt local file is
  refused before any PUT. The execution receipt records a top-level `forced_reupload` boolean.
- **A real multipart (`part_count>1`) is now recognized as an upload tier2 proof**, alongside
  the existing 5 GiB `bytes_uploaded` path. A forced small multipart can therefore prove
  upload tier2 for a store with no >5 GiB object. The adopt tier ladder is unaffected.
- **No migration; default behavior and existing receipts/manifests are byte-identical.** With
  the flag absent, every path is unchanged; a default receipt gains only an always-present
  `forced_reupload: false` boolean.
- See `wom-kit/docs/releases/v0.3.175.md`.

## From `v0.3.173` To `v0.3.174`

One additive fix to the verified-adopt tiered gate. No migration is required; existing
receipts and manifests are unaffected, and the object-storage-upload tier ladder is
byte-identical.

Operator-visible notes:

- **Adopt tiered gating is decoupled from the upload 5 GiB multipart proof.** A verified
  `object-storage-adopt-existing --approve` is HEAD-only (it moves zero bytes), so it no
  longer needs a store proven to the object-storage-upload tier 2 (a 5 GiB / multipart PUT
  proof). It now uses a binary adopt-specific gate: a single tiny-first adopt is always
  permitted, and exactly one prior verified tiny-first adopt unlocks a batch adopt of any
  size. Operator remedy for a large handover: run `object-storage-adopt-existing --only
  <one-sha> --approve` once, then re-run the full `--key-map` batch.
- **Adopt blocker token renamed.** The adopt gate blocker is now `adopt_tiny_first_unmet`
  (was `tiered_gate_unmet`). The object-storage-upload gate keeps `tiered_gate_unmet`
  unchanged. Update any script that matched the adopt blocker string.
- **No migration; nothing else changes.** Existing execution receipts and manifest locations
  are unaffected. An upload receipt still never unblocks adopt, a declared/unverified adopt
  still never counts and never gates a PUT, and a wrong `--key-map` still self-limits to zero
  adopts.
- See `wom-kit/docs/releases/v0.3.174.md`.

## From `v0.3.172` To `v0.3.173`

One additive command. No migration is required, and every default path is byte-identical to
v0.3.172.

Operator-visible notes:

- **New `archive migrate --target base-link-types --dry-run|--approve --reviewed-by
  <actor>`.** It appends every base WOM-kit link type missing from an archive-local
  `zettel-kasten/types.yml` (a superset of the recommended-9 `link-types-v0.3` set — it also
  pulls `continues`). It is append-only and no-clobber: no existing entry is removed,
  renamed, reordered, or altered in value, so a divergent same-id customization always wins
  (reported under `present_not_overwritten`). `--reviewed-by` is required with `--approve`.
  It writes a receipt (`receipt_kind: base_link_types_sync`) under
  `receipts/migrations/base-link-types.*.migration.json`, is atomic with rollback, and is
  idempotent. There is deliberately **no `--revert`** (`--revert --target base-link-types`
  fails closed). No change if you do not run it.
- **Safe no-op with no local `types.yml`.** If your archive has no local
  `zettel-kasten/types.yml`, the sync writes nothing and creates no file — you already
  inherit all current and future base link types. Do not add a local `types.yml` just to run
  this; a local `types.yml` permanently shadows (freezes) the base.
- **Doctor routing.** `archive doctor` now points an operator hitting an undefined edge type
  toward `archive migrate --target base-link-types --dry-run`.
- **Honesty.** Once an archive has its own `types.yml`, it shadows the base permanently, so
  every future base link type also needs a manual `migrate --target base-link-types` (no
  automatic propagation). Sync copies base entry shapes as of this release (a snapshot). It
  normalizes/rewrites the whole `types.yml` via `safe_dump` — comments, anchors, flow-style,
  and key ordering may be normalized — exactly like the sibling `link-types-v0.3` migration.
  Existing entries are preserved by value/id; surrounding formatting is not byte-preserved.
  Review the diff.
- See `wom-kit/docs/releases/v0.3.173.md`.

## From `v0.3.171` To `v0.3.172`

Two verification-honesty fixes. Both are additive; no migration is required, and every
default path is byte-identical to v0.3.171.

Operator-visible notes:

- **New `--multipart-part-size <BYTES>` and `--allow-tiny-parts` on
  `object-storage-upload`.** Default part size (64 MiB) is unchanged. An override is
  bounded to `[4096, 64 MiB]`, and below the default it requires `--allow-tiny-parts`.
  Paired with a lowered `--multipart-threshold`, it forces multipart on a small object so
  you can prove LIVE R2 multipart. It changes only how the file is fragmented for reads;
  the whole-object before-hash, the HEAD-after full-object verify, orphan cleanup, and the
  leak gate are unchanged. Real R2 rejects multipart parts smaller than 5 MiB except the
  last, so a tiny part size is a live-verification aid — a live tiny-part rejection is an
  upload rejection (failed status), never a silent integrity bypass. No change if you do
  not pass the flag.
- **Additive receipt field.** The object-storage upload execution receipt gains
  `effective_multipart_part_size_bytes`. The schema is non-breaking (no
  `additionalProperties:false`; the field is not `required`). Existing receipts and
  consumers are unaffected.
- **Strip-bom dry-run parity.** `--strip-bom` on a `--dry-run` of `remint-reconcile` and
  `retire-draft-reconcile` now previews the same strip-intent metadata (`bom_stripped`,
  `bom_strip_note`) an `--approve` run records. This is a strict classification no-op:
  `drift_class` and the content-change ack requirement are identical whether `--strip-bom`
  is passed or not, so a real `content_change` is never laundered to `format_drift`.
- See `wom-kit/docs/releases/v0.3.172.md`.

## From `v0.3.170` To `v0.3.171`

This release adds one opt-in flag, `--key-map`, to `object-storage-adopt-existing`.
It is additive and adopt-only: the default path (no `--key-map`) is byte-identical to
v0.3.170, and `object-storage-upload` is unchanged. No migration is required.

Operator-visible notes:

- **New `--key-map <file>` on `object-storage-adopt-existing`.** Hand WOM the exact
  existing remote key per object, as JSONL, one object per line:
  `{"sha256":"<64hex>","remote_key":"<key>"}`. For a mapped object the map value is
  the resolved key verbatim, so `--key-strategy`/`--key-prefix`/
  `--key-append-extension` are ignored for that object. Use this when objects already
  live under your own per-object filename extension that the content-addressed
  template cannot recover (the prehashed-ledger case, where the manifest logical_key
  has no extension). Objects with no map entry are reported and NOT adopted.
- **Safety is unchanged and stronger.** Size is always sourced from the manifest, not
  the map; a mapped key that 404s or size-mismatches re-uploads rather than
  false-skipping; each key must digest-bind (the object's sha256 as a path segment or
  filename stem) and pass the leak guard; a malformed or ambiguous map is whole-run
  fatal and adopts nothing. For any map you did not mechanically generate from a
  trusted per-object upload record, add `--content-hash-verify` — it is the only
  cryptographic proof against a same-size, different-bytes object.
- **No change if you do not use it.** Without `--key-map`, adopt behaves exactly as in
  v0.3.170. See `wom-kit/docs/releases/v0.3.171.md` and the runbook
  `wom-kit/docs/object-storage-adopt-existing-key-map-runbook.md`.

## From `v0.3.169` To `v0.3.170`

This release adds runtime AI-operator discipline norms. It is docs-only and
additive: no command, schema, receipt, or archive change, and no new
WOM-enforced check. No migration is required.

Operator-visible notes:

- **New `AI-Operator Discipline` section on the runtime surfaces.** The three
  `AGENTS.md` templates (personal/company/family), the runtime `SKILL.md`, and
  `wom-ai-runtime-skill-plugin-layer.md` now carry three behavioral norms an
  operator AI applies: record the source the human actually encountered and never
  silently substitute a "more authoritative"/original one; enumerate the
  installed/available tools before declaring a task impossible or degrading it; and
  carry forward already-established/approved state instead of re-asking. If you have
  copied an older `AGENTS.md` into a real archive, you may add the new section, but
  nothing breaks if you do not — it changes no command behavior.
- **New source-substitution axis in `text-provenance-hierarchy.md`.** A `## 7.
  Encountered-Source Fidelity` subsection names both provenance axes explicitly (the
  existing derivation-tool axis and the new source-substitution axis). Documentation
  only; the provenance model gains no new required field.
- **Guidance, not enforcement.** WOM does not validate provenance fidelity, tool
  enumeration, or state carry-over, and this release adds no check that does. The
  `ai-response-concept-guide` topic enum is unchanged. See
  `wom-kit/docs/releases/v0.3.170.md`.

## From `v0.3.168` To `v0.3.169`

This release adds a read-only operator-feedback delivery ledger and an
approval-gated batched mark-delivered command. All changes are additive; no
migration is required.

Operator-visible notes:

- **No archive migration; existing records unchanged; no hash change.** The
  `operator-feedback.schema.json` record gains two OPTIONAL string properties,
  `delivered_at` and `acknowledged_at` (not added to `required`), so existing
  `ops/feedback/*.yml` records validate and are read as-is. A new
  `operator-feedback-delivery-receipt.schema.json` ships for the batch receipt.
- **New read-only `archive operator-feedback-ledger`** (aliases `feedback-ledger`,
  `feedback-board`): aggregates delivery-status counts + a pending (draft) list +
  the newest delivery boundary from `ops/feedback/*.yml`. It writes nothing, reads
  no feedback body, and echoes no feedback ref, title, path, token, or secret
  values. Malformed records are counted as `unreadable` and skipped. Records
  delivered via the older `--status delivered` path have no `delivered_at`, so the
  boundary falls back to their `updated_at`.
- **New approval-gated `archive operator-feedback-mark-delivered`** (alias
  `feedback-mark-delivered`): `--dry-run` previews the draft->delivered transitions
  and writes nothing; `--approve --reviewed-by <actor>` marks every pending `draft`
  record delivered, stamps `delivered_at`, and writes one batch receipt. `--only
  <id>` marks a single record. It only touches `draft` records, is idempotent, and
  skips malformed records without half-writing others.
- **Truth boundary (no overclaim).** This is metadata lifecycle only.
  `external_submission_performed` stays `false`; `delivered` means the operator
  marked it delivered, not that anything was submitted externally or proven
  received. See `wom-kit/docs/releases/v0.3.169.md`.

## From `v0.3.167` To `v0.3.168`

This release adds draft-time identity hygiene, an attributed mint affirmation flag,
a discoverability pointer to retire consumed drafts, a base `continues` edge type,
and draft-time `--kind` validation. All changes are additive; no migration is
required.

Operator-visible notes:

- **No archive migration; existing ids unchanged; no hash change.** No existing
  canonical id is renamed or normalized. The mint receipt gains a new additive
  `affirmations` array (`item_id`, `affirmed_by`, `affirmed_at`), and the mint result
  gains a `next_safe_actions` string list; `mint-receipt.schema.json` uses no
  `additionalProperties: false`, so existing receipts, manifests, and zets are
  accepted as-is.
- **Draft-id hygiene (forward-only).** A NEW draft whose title has no ASCII
  alphanumerics (a titleless or pure-Hangul title) now gets a `zet_<ts>_note` id
  instead of the old `zet_<ts>_draft` fallback. This affects only newly created
  drafts; existing ids are untouched and mint gains no id-rewrite path.
- **Attributed `--affirm` on `mint-zet`.** `mint-zet --approve --reviewed-by <actor>
  --affirm <item_id>` (repeatable; accepts only `one_clear_purpose`,
  `sensitive_content_reviewed`) satisfies the two human-review checklist items via an
  audited, reviewer-attributed CLI act instead of a raw `mint.checklist` YAML edit,
  recorded in the receipt's `affirmations` block. It is inert without `--reviewed-by`
  (hard error), cannot override machine-enforced items, and never flips an explicit
  YAML `false`. **Honest residual:** like the pre-existing `--reviewed-by` gate,
  `--affirm` cannot prove the reviewer string names a real human; it adds no new
  self-affirm hole and its guarantee is attribution and auditability, not
  string-sniffing.
- **Retire pointer, no auto-delete.** A successful mint result now points to
  `archive retire-draft --zettel-id <id> --dry-run` via `next_safe_actions` (printed
  in text mode). Mint still never deletes the consumed inbox draft; retirement stays
  its own approval-gated step.
- **Base `continues` edge type.** The base `zettel-kasten/types.yml` (KIT and
  fixture) now defines a `continues` link type for a same-thread continuation.
  **Limitation:** it is base-only and NOT part of the `migrate link-types-v0.3`
  recommended set, so archives that vendored their own `types.yml` add the entry
  manually (it is additive).
- **Draft-time `--kind` validation + `--list-kinds`.** `archive create-draft`
  now warns (does not block) on a `--kind` not in the archive's `zettel-rules.yml`
  and lists the valid kinds; `archive create-draft --list-kinds` lists them read-only
  and writes nothing. See `wom-kit/docs/releases/v0.3.168.md`.

## From `v0.3.166` To `v0.3.167`

This release extends the honest reconcile family (snapshot-drift-aware
classification, a `retire-draft-reconcile` sibling, an opt-in `--strip-bom`),
fixes the object-storage run-outcome `live_execution_allowed_now` field, and adds
a bounded `--multipart-threshold` testing aid. All changes are additive; no
migration is required.

Operator-visible notes:

- No archive migration and no hash change. Two new fields on the mint reconcile
  audit receipt (`classification_basis`, `bom_stripped`), a new `reconcile`
  provenance block on retire receipts, a new `retire-draft-reconcile-receipt.schema.json`,
  and two new fields on the object-storage upload receipt
  (`effective_multipart_threshold_bytes`, `part_count`) are all additive. No schema
  uses `additionalProperties: false`, so existing receipts, manifests, and zets are
  accepted as-is.
- `remint-reconcile` now recognizes a `format_drift` even when the draft snapshot
  itself drifted, but only behind two independent proofs and a full-field frontmatter
  check (an all-fields reconstruction over every content field plus an `id`/`title`
  cross-check against the mint receipt) — so a canonical edit to any content field
  (`visibility`, `kind`, `facets`, …), or a content-tampered snapshot, can never
  anchor `format_drift`. Any uncertainty still classifies `content_change` and
  requires `--content-changed-ack`.
- The reconcile classification test
  `test_remint_reconcile_drifted_snapshot_falls_back_to_content_change` was revised:
  its content subscenarios are unchanged (still `content_change`), and new pure-format
  subcases were added in a sibling test that flip to `format_drift`.
- New CLI-only command `archive retire-draft-reconcile --dry-run|--approve` reconciles
  a retire-draft receipt's four refs; the doctor now routes the
  `mint_retired_draft_sha_mismatch` finding to it via a `suggested_command`.
- New opt-in `--strip-bom` on both reconcile commands removes exactly a leading
  UTF-8 BOM (`format_drift` by definition) and never bypasses the content-change ack
  gate. New `--multipart-threshold BYTES` on `object-storage-upload` is a
  validation/testing aid bounded to `[64 MiB, 5 GiB]`. See
  `wom-kit/docs/releases/v0.3.167.md`.

## From `v0.3.165` To `v0.3.166`

This release makes the object-storage upload key selectable and recorded, adds a
safe `object-storage-adopt-existing` workflow, and hardens the skip rule so an
object stored under an operator's own key layout is never re-uploaded — or, worse,
falsely skipped.

Operator-visible notes:

- No archive migration is required, and no hash change. The default key strategy
  is byte-identical to v0.3.165: the two-field model is additive. Every
  object-storage location and execution receipt now also records a `remote_key`
  (the literal bucket-relative key the object is/was PUT/HEAD at) next to the
  unchanged content-addressed `key_hint`. Existing receipts, manifests, and zets
  are unaffected; the doctor accepts them as-is.
- New opt-in flags on `object-storage-upload`, `object-storage-upload-plan`, and
  `object-storage-upload-verify`: `--key-strategy {sha256_content_addressed,
  prefix}` (default `sha256_content_addressed`), `--key-prefix <literal>` (the raw
  bucket-relative prefix; a colon in an archive-id is a legal key byte), and
  `--key-append-extension` (append the recovered original-filename extension only,
  and only when recoverable — no bare trailing dot otherwise).
- New command `archive object-storage-adopt-existing --dry-run|--approve`. Use it
  BEFORE a first `--approve` upload if your objects already live under your own key
  layout. A verified adopt (with `--approve` + live credentials) HEADs each key
  presence-only and adopts ONLY on presence + Content-Length size-match (NOT a
  content hash — the presence-only HEAD does not download the object body, so
  adopting a large archive costs one HEAD per object, not one download per object;
  add `--content-hash-verify` per object to additionally GetObject-and-rehash). A
  404 / size-mismatch is not adopted, so a wrong `--key-prefix` or extension simply
  re-uploads those objects. A declared adopt (`--accept-unverified-adopt`, a flag
  distinct from `--approve`) records a NON-gating `declared_uploaded` location that
  never skips a PUT. Adopt reports adopted-vs-total so a template miss is visible.
  Verified adopt is a live surface and honours the same tiny-first tiered gate as
  the upload command: a bulk first-live adopt REFUSES with `tiered_gate_unmet`
  until a single tiny-first object (`--only <id>`) has proved the store.
- Idempotency is now HEAD-verified. Under a live transport the executor always
  re-HEADs the recorded `remote_key` before skipping; a recorded key that 404s
  re-uploads. The re-HEAD matches how the location was verified: a presence+size
  adopt is re-checked presence-only (no download), a content-hashed upload keeps its
  checksum re-check. This live proof outranks the resume ledger — once a re-HEAD
  proves an object absent, the re-upload is forced past any stale terminal-success
  ledger row, so a wiped remote is never silently skipped. Plan echoes the resolved
  key and apply refuses (fails closed) on divergence; the plan verdict is
  strategy-aware so it never predicts a skip apply would not honour. See
  `wom-kit/docs/releases/v0.3.166.md`.

## From `v0.3.164` To `v0.3.165`

This release adds a normative Plain-Language for Humans convention to the
operator-facing runtime surfaces and a git/infrastructure terminology
translation layer to the read-only `ai-response-concept-guide`.

Operator-visible notes:

- No archive migration is required, and no hash change. The additions are
  guidance prose (in the `AGENTS.md` templates, the runtime skill, and the
  plugin-layer doc) plus a new read-only `--topic git_infra_terms` set on
  `ai-response-concept-guide`. Existing receipts, manifests, and zets are
  unaffected.
- Guidance, not enforcement. The convention tells an operator AI to translate
  git/infrastructure/WOM-internal jargon into everyday language for humans while
  keeping the exact term in parentheses or logs. WOM does not validate or enforce
  plain-language output; the reading AI applies it. Machine, JSON, and receipt
  output stays exact and unchanged.
- Look up the plain phrasing with `archive ai-response-concept-guide
  <archive-root> --topic git_infra_terms --locale en-US --dry-run --format json`.
  It writes nothing, calls no providers, and echoes no local paths or secret
  values. See `wom-kit/docs/releases/v0.3.165.md`.

## From `v0.3.163` To `v0.3.164`

This release adds Stage 2 of the object-storage upload adapter (WOM #11): a real
AWS SigV4 R2/S3-compatible upload transport. WOM is now network-CAPABLE for an
approved object-storage upload, but capable is not automatic.

Operator-visible notes:

- No archive migration and no hash change. Existing receipts and manifests are
  unaffected until you choose to run an upload command.
- At this v0.3.164 checkpoint the transport added no dependency. It is
  hand-rolled `hashlib`/`hmac`/`base64` over the existing `urllib` seam, so
  `wom-kit/pyproject.toml` remained PyYAML-only at that time. v0.3.295 later
  added the separately scoped pinned `unicodedata2` normalization dependency.
- A live `--approve` upload requires ALL of: env-only credential refs
  (`--access-key-id-ref env:...` and `--secret-access-key-ref env:...`), a safe
  `--reviewed-by`, a resolvable non-secret `--endpoint-host` and `--bucket`
  (region defaults to `auto` for cloudflare-r2), and a met tiered tiny-first gate.
  A bulk first-live run REFUSES with `tiered_gate_unmet` until the single small
  object is proved first. A hard cumulative PUT ceiling bounds cost across the run.
- Validate live tiny-first. Upload ONE small object end-to-end, verify the
  execution receipt + manifest `wom_uploaded` transition + remote after-HEAD by
  hand, then advance tiers. The release note ships the exact runbook. Receipts and
  the release note carry `unproven_against_live_provider: true` until the first
  live object is confirmed. See `wom-kit/docs/releases/v0.3.164.md`.

## From `v0.3.162` To `v0.3.163`

This release adds Stage 1 of the object-storage upload adapter (WOM #11) as three
new approval-gated commands, plus an additive hardening of the shared
object-storage manifest writer.

Operator-visible notes:

- New commands only; nothing runs automatically. `archive
  object-storage-upload-plan --dry-run` and `archive object-storage-upload-verify
  --dry-run` are read-only and write nothing. `archive object-storage-upload`
  requires exactly one of `--dry-run`/`--approve` and a safe `--reviewed-by` with
  `--approve`.
- The adapter CANNOT upload yet. This is Stage 1 of a staged rollout: no live
  transport ships, so `archive object-storage-upload --approve` fails closed with
  `live_transport_not_implemented` before any credential read or byte read. There
  is no env var or flag that reaches a provider; a Stage-2 code change is required.
- No archive migration and no hash change. The manifest-write hardening is
  additive: the shared object-storage manifest writer now holds the manifest lock
  and writes atomically (temp+fsync+os.replace), which also protects the existing
  `object-storage-upload-evidence` command. Existing receipts and manifests are
  unaffected until you choose to run an upload command.
- Added `wom-kit/schemas/object-storage-upload-receipt.schema.json`, a doctor
  check for object-storage execution receipts, and read-only MCP tools
  `object_storage_upload_plan` and `object_storage_upload_verify`. See
  `wom-kit/docs/releases/v0.3.163.md`.

## From `v0.3.161` To `v0.3.162`

This release adds `archive remint-reconcile`, an honest way to re-issue a mint
receipt's recorded sha256 values after a canonical zet drifts on disk. It also
adds additive BOM/newline parse tolerance and a doctor/retire route to the new
command.

Operator-visible notes:

- New command only; nothing runs automatically. `archive remint-reconcile
  <archive-root> (--zettel-id <id> | --path <rel>) [--dry-run | --approve]
  [--reviewed-by <actor>] [--content-changed-ack]` classifies a canonical zet's
  drift as `format_drift` (newline/BOM only) or `content_change`, always shows
  the on-disk content, and requires `--reviewed-by` to approve (a
  `content_change` also requires `--content-changed-ack`). See
  `wom-kit/docs/mint-receipt-reconcile.md`.
- No archive migration and no hash change. BOM/newline tolerance affects
  parse/read helpers only; sha256 still reads raw bytes, so BOM and newline
  drift stay visible as a sha mismatch. Existing receipts and canonical files
  are unaffected until you choose to run `remint-reconcile`.
- STRICT-GATE NOTE (surfacing, not new failures): a canonical zet whose bytes
  already drifted by newline/BOM from its mint receipt was already failing
  `doctor`/`--strict` with `mint_receipt_sha_mismatch`. From v0.3.162 that same
  case carries a suggested `remint-reconcile --dry-run` command, a UTF-8 BOM on
  a canonical zet adds a `zettel_has_bom` WARN, and a previously-reconciled
  receipt that re-drifted by newline/BOM only reports the distinct
  `mint_receipt_target_byte_drift_suspected_format` ERROR. All stay ERRORs; the
  edge-receipt evolution path is unchanged and no gate was relaxed.
- New mints pin the canonical write to LF newlines to prevent immediate
  re-drift. Added `wom-kit/schemas/mint-reconcile-receipt.schema.json` and a
  `reconcile` object property on `mint-receipt.schema.json` (not required;
  legacy receipts validate unchanged). See
  `wom-kit/docs/releases/v0.3.162.md`.

## From `v0.3.159` To `v0.3.160`

This release adds the AI intake protocol (source-intake before any physical
file copy), two objet-store git guards in doctor, the `/objets/` gitignore
safe default, the D2 intake layout ruling, and operator-feedback
discoverability plus schema files.

Operator-visible notes:

- STRICT-GATE IMPACT (deliberate, not merely additive), in two tiers. First,
  EVERY archive created before v0.3.160 — with or without an `objets/`
  folder — now trips the pre-existing `local_profile_gitignore_incomplete`
  warning, because `/objets/` joined the recommended `.gitignore` defaults;
  that alone fails `archive validate` (fails on warnings unless
  `--allow-warnings`) and `archive doctor --strict` until one
  `archive repair-gitignore <archive-root> --approve --reviewed-by <actor>`
  run adds the line. Second, the new doctor warnings
  `archive_objets_layout_noncanonical` (a raw in-root `objets/` folder
  exists) and `workspace_objet_store_git_exposure` (an objet byte store may
  be tracked by an enclosing git working tree) can fail the same gates plus
  `archive runtime-context --strict` for archives that keep originals in an
  in-root `objets/` folder or an exposed store — until the migration guide
  in `wom-kit/docs/artifact-hygiene.md` section 5 is followed. The layout
  warning is intentionally NOT silenced by gitignoring the folder: ignored
  originals silently drop out of the git-push backup path, so the reminder
  stays loud until the folder is emptied through the reviewed capture chain.
- Gitignore additions are additive lines only: `/objets/` (anchored — nested
  `objets/` folders inside staged trees are unaffected) joins the recommended
  defaults; existing archives pick it up with
  `archive repair-gitignore <archive-root> --approve --reviewed-by <actor>`
  (until then the completeness warning fails strict gates, as above).
  Two honest gitignore caveats: it does not untrack already-committed files
  (human-reviewed `git rm --cached` if that happened), and the sibling
  `<root-name>-objets` store is NOT matched by `objets/` — the exposure
  warning names the store's actual directory name, as an anchored
  `/<name>/` line when the store is a direct child of the repository root
  and as an unanchored `<name>/` line when it sits deeper (an anchored
  repo-root line would not match a nested store in git).
- JSON consumers see additive fields only: `staging_convention` gains
  `matched_shape`, `recommended_in_archive_shape`, and
  `in_archive_staging_supports_capture`; `recommended_first_commands` gains a
  fourth (appended) operator-feedback-plan entry; `ai_runtime_order` gains
  step 7 `plan_operator_feedback`; `available_safe_actions` gains
  `run operator-feedback-plan dry-run` INSERTED mid-list next to the other
  read-only dry-run actions (position 3 of 8). Consumers that pinned the FULL
  `ai_runtime_order` list, the exact `recommended_first_commands` length, or
  `available_safe_actions` positions must account for the new entries.
- In-archive staging is now canonical: folders under
  `<archive-root>/staging/incoming/` report
  `follows_staging_convention: true` from project-intake-plan and
  project-intake-unpack-queue instead of `outside_recommended_shape`, and
  project-intake-staging-guide (which takes no staged folder) recommends the
  same in-archive shape for capture intake via the additive
  `recommended_in_archive_shape` / `in_archive_staging_supports_capture`
  fields. The sibling
  `zettel-kasten-<profile_slug>-objets\intake\<project_slug>` shape stays
  accepted for bulk external originals.
- New schema files `wom-kit/schemas/operator-feedback.schema.json` and
  `wom-kit/schemas/operator-feedback-receipt.schema.json` describe the
  UNCHANGED shipped record/receipt shapes; schema-id strings are unchanged
  (`wom-kit/operator-feedback/v0.1`,
  `wom-kit/operator-feedback-receipt/v0.1`). No record migration.
- No archive migration is required. See
  `wom-kit/docs/releases/v0.3.160.md` and
  `wom-kit/docs/artifact-hygiene.md`.

## From `v0.3.158` To `v0.3.159`

This release adds paired transcript intake (one approval covers a staged
original plus its already-extracted transcript) and BOM-aware derive-text
encoding.

Operator-visible notes:

- ADDITIVE manifest field + NEW action string: a selection item MAY carry a
  `derived_text` sub-object (`staged_text_path`, `approved_text_sha256` over
  RAW bytes, `derivation_kind`, `tool_name`, `tool_version`, `review_status`,
  optional model/confidence/language/born_digital). Paired manifests MUST use
  `action: local_objet_capture_with_derived_text_approved` and `schema:
  wom-kit/b4-selection/v0.3`. Kits at v0.3.158 or earlier refuse paired
  manifests with `selection_action_invalid` — fail-closed by design. The
  mechanism matters: the old envelope validator ignores the `schema` field
  (it was write-only) and ignores unknown item keys, so the ACTION string is
  the only lever that makes old kits refuse instead of silently capturing the
  original and dropping the approved derived half. v0.3.159 starts validating
  the `schema` field (`selection_schema_invalid`): plain manifests require
  the v0.2 schema every generated manifest already carries; hand-built
  manifests without a `schema` field must add it.
- utf-8-sig hash-identity change (NOT additive): before this release a UTF-8
  BOM survived validation and the raw bytes were stored WITH the BOM. The BOM
  is now stripped before storage, so the same utf-8-sig input produces a
  different `text_sha256`/`derived_text_id` than a pre-upgrade capture, and a
  post-upgrade re-run of that input creates a SECOND record instead of
  `skip_already_present`. BOM-less UTF-8 input is unaffected (stored bytes ==
  raw bytes).
- Receipt schema bumps: `wom-kit/objet-capture-receipt/v0.2` ->
  `wom-kit/objet-capture-receipt/v0.3` (items may carry a `derived_text`
  sub-result; additive `status_class` at item and run level; derived summary
  counters on paired runs) and `wom-kit/derived-text-capture-receipt/v0.1` ->
  `wom-kit/derived-text-capture-receipt/v0.2` (`source_text_encoding`,
  `source_text_sha256`, and `paired_with` on paired registrations). The
  derived-text RECORD schema stays `wom-kit/derived-text-record/v0.1` with
  additive optional provenance fields.
- New blockers: `approved_text_content_mismatch`, `unsafe_staged_text_path`,
  `blocked_by_original`, `derived_text_registration_failed`,
  `selection_schema_invalid`, `text_file_bom_encoding_unsupported`,
  `text_file_bom_encoding_undecodable`, `text_file_contains_nul`,
  `text_file_too_large`. `text_file_not_utf8` is now raised for BOM-less
  non-UTF-8 input only and gains a static hint. Paired-manifest metadata
  validation reuses the existing derive-text `*_invalid` vocabulary
  (`derivation_kind_invalid`, `review_status_invalid`, `tool_name_invalid`,
  `tool_version_invalid`, `confidence_invalid`, `language_invalid`,
  `born_digital_invalid`) and adds `model_name_invalid` /
  `model_version_invalid` for non-string optional model fields.
- No archive migration is required. See
  `wom-kit/docs/releases/v0.3.159.md` and the Encoding section of
  `wom-kit/docs/derived-text.md`.

## From `v0.3.157` To `v0.3.158`

This release adds owner-approved real-archive objet capture enablement.

Operator-visible notes:

- New CLI command `archive objet-capture-enable <archive-root>` (alias
  `archive capture-enable`): `--dry-run` is a read-only eligibility report;
  `--approve --reviewed-by <actor>` writes a receipt under
  `receipts/capture-enablement/` first and the singleton
  `ops/capture-enablement.yml` consent record second; `--revoke --approve`
  revokes; pattern-matched root names require
  `--acknowledge-never-touch-name`; re-approving over a revoked record
  requires `--reenable`. The command is CLI-only and not exposed via MCP.
- No JSON fields are renamed. `objet-capture` refusals gain one ADDED field,
  `enablement_state`; the `blocked_by` ids are unchanged.
- The hint TEXT of both `objet-capture` refusal hints changed (hints are
  static strings, not a parsing contract). Downstream copies of the
  `"separate planned flow"` substring assertion need the same update.
- Per-item never-touch semantics change for validly-enabled roots only:
  the pattern is evaluated on archive-relative components below the enabled
  root. Non-enabled roots, including all sandbox-marked archives without an
  enablement record, behave exactly as before.
- No archive migration is required. See `wom-kit/docs/capture-enablement.md`
  and `wom-kit/docs/releases/v0.3.158.md`.

## From `v0.3.4` To `v0.3.5`

This release is a compatible field-feedback fast-follow for derived-text
registration and local archive hygiene.

What changed:

- v0.3 historically added batch registration of already extracted UTF-8 derived text; in v0.4.0 use `archive derive-text capture <archive-root> --from-manifest <jsonl> --dry-run` only, and approval is fixed closed before private reads,
- batch manifests are JSONL: each line uses `source_object_id`, `text_file`, `derivation_kind`, `tool_name`, `tool_version`, and `review_status`, with optional `item_id`, `model_name`, `model_version`, `confidence`, `language`, and `born_digital`,
- relative `text_file` values resolve from the JSONL manifest location, and archive records do not store the local text file path,
- added CLI `archive repair-gitignore <archive-root> --dry-run|--approve --reviewed-by <actor>` to append missing WOM-kit safe `.gitignore` patterns while preserving existing entries,
- removed private dogfood archive identifiers from public guardrail code and docs while keeping generic live-archive and local `*-objets` protections,
- updated version metadata to `0.3.5`.

No frontmatter or manifest migration is required for v0.3.4 users.

`repair-gitignore` does not delete or rewrite existing `.gitignore` entries,
clean files, inspect source file bodies, upload, sync, or call provider APIs.
`derive-text capture --from-manifest` still does not run OCR, ASR, parsers, LLM
vision, provider APIs, drafting, or minting.

## From `v0.3.3` To `v0.3.4`

This release adds the first derived text capture layer.

What changed:

- v0.3 historically added single-file derived-text registration; in v0.4.0 use `archive derive-text capture <archive-root> --text-file <file> --source-object-id <object-id> --derivation-kind <kind> --tool-name <name> --tool-version <version> --review-status <status> --dry-run` only, and approval is fixed closed before private reads,
- added `objects/manifests/derived-text.jsonl` for provenance-aware derived text records,
- approved capture stores UTF-8 text bodies under `objects/derived-text/sha256/` and writes `receipts/derived-text-capture/*.json`,
- `archive index` ingests derived text records and `archive search` can return `type: derived_text`,
- doctor validates derived text JSONL, source object references, vocabulary, and stored text hashes when present.
- updated version metadata to `0.3.4`.

The source object must already exist in `objects/manifests/files.jsonl`.
`derive-text capture` does not run OCR, ASR, parsers, LLM vision, provider APIs,
drafting, or minting. Rebuild the generated search index after approved derived
text capture:

```text
archive index <archive-root>
```

## From `v0.3.2` To `v0.3.3`

This is a compatible field-feedback hardening release.

What changed:

- CLI output is resilient to console encodings that cannot represent every character,
- doctor and validate now fail more clearly on unquoted YAML timestamp frontmatter,
- `validate --strict` is accepted for parity with doctor,
- `staged-cleanup-check` exits `0` only when `safe_to_cleanup` is true; unsafe cleanup reports exit `1`,
- `view-zets` can match scalar facet filters against list-valued zettel facets after re-indexing,
- list-valued view filter inputs block instead of being guessed or broadened,
- objet-capture source-intake plan SHA binding is regression-tested with a real `source-intake --dry-run` producer plan through dry-run and approve,
- updated version metadata to `0.3.3`.

Archives authored under v0.3.2 rules need no schema migration. If you rely on
facet views, rebuild the disposable search index once:

```text
archive index <archive-root>
```

If you automate staged-folder cleanup checks, treat the new nonzero exit on
unsafe reports as expected fail-closed behavior and read the JSON
`safe_to_cleanup` field before any manual cleanup decision.

This release does not touch live archives, providers, ZET transport, MCP write
tools, cleanup targets, or the v0.3.1 frontmatter schema itself.

## From `v0.3.1` To `v0.3.2`

This release ships the frontmatter v0.3 compatibility migration, the local objet
capture spine, and consistent redacted-zettel suppression.

What changed:

- added approval-gated CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run|--approve --format json`,
- added approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` writing content-addressed objets, manifest records, and capture receipts into sandbox-marked archives only,
- added report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run`,
- added read-only CLI `archive related-zets` (typed-edge backlinks) and `archive view-zets` (facet view execution),
- indexed typed edges and zettel facets in the disposable search index,
- enforced redacted-zettel content suppression across search, the index, list-zettels, read-zettel, block-header previews, projection previews, related-zets, and view-zets,
- added the report-only artifact hygiene checker and file-lifecycle baseline,
- updated version metadata to `0.3.2`.

Archives authored under v0.3.1 rules need no frontmatter changes; the v0.3.1
schema is unchanged. Archives authored from older v0.2-draft frontmatter rules
should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation, and apply only after reviewing the plan on a
backup or sandbox copy.

Rebuild the local search index once to pick up edges and facets:

```text
archive index <archive-root>
```

The objet-capture write path refuses archives without an explicit sandbox marker
(`.wom-sandbox` file or top-level `environment: sandbox`). This release does not
touch live archives, providers, ZET transport, MCP write tools, or the v0.3.1
schema itself.

## From `v0.3.0` To `v0.3.1`

This is a compatible read-only route-preview release.

What changed:

- added CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before returning any route pointer,
- added route pointer fields for `delegate`, `attest`, `anchor`, and `none`,
- added explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardened route selection so free-form or hostile `proposed_action` metadata is not echoed,
- added `wom-kit/docs/shared-update-route-preview.md`,
- updated version metadata to `0.3.1`.

The route-preview command itself requires no provider, transport, or
shared-update record migration. Archives authored from older v0.2-draft
frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command is read-only and dry-run only. It writes no files and only points a human toward an existing canonical command surface. It does not expose an MCP write/apply/approve tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, attestations, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.60` To `v0.3.0`

This is a compatible first v0.3.0 write-boundary release.

What changed:

- added CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before writing,
- added deterministic receiver-side review record and receipt paths,
- added replay/overwrite refusal and receipt-failure rollback,
- added `wom-kit/docs/shared-update-attestation-review-write.md`,
- updated version metadata to `0.3.0`.

The shared-update attestation/review command itself requires no provider,
transport, or shared-update record migration. Archives authored from older
v0.2-draft frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command writes only a local shared update attestation/review record and matching receipt. It does not expose an MCP write/apply tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.59` To `v0.2.60`

This is a compatible documentation, version, and test checkpoint for the v0.2.x freeze and v0.3.0 entry boundary.

What changed:

- added `wom-kit/docs/v02x-freeze-v03-entry-boundary.md`,
- added the v0.2.60 release note and public-safe work log,
- updated the capability matrix with the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- updated version metadata to `0.2.60`.

No private archive migration is required.

This release adds no product CLI command, MCP tool, archive service behavior, or schema change. It records that the proposed v0.3.0 first boundary should be one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, feed updates, trust/import/acceptance/anchor mutation, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, DID registry, wallet/key custody, public proof anchoring, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.58` To `v0.2.59`

This is a compatible read-only ZET transport threat model and would-transport planning patch.

What changed:

- added CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- added MCP `zet_transport_would_plan`,
- added service `zet_transport_would_plan`,
- added `wom-kit/docs/zet-transport-threat-model.md`,
- updated version metadata to `0.2.59`.

No private archive migration is required.

The new command reads one local archive-contained shared update record JSON, reuses the v0.2.56 single-record review preview policy, writes nothing, and returns a planning-only risk/control preview for a future transport method. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.57` To `v0.2.58`

This is a compatible read-only shared update review index patch.

What changed:

- added CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_index`,
- added `wom-kit/docs/zet-shared-update-record-review-index.md`,
- updated version metadata to `0.2.58`.

No private archive migration is required.

The new command inspects only direct-child local JSON records under an archive-relative directory, reuses the v0.2.56 single-record review policy, writes nothing, and returns a compact deterministic index. It does not add shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.56` To `v0.2.57`

This is a compatible capability matrix and README readability patch.

What changed:

- added `wom-kit/docs/capability-matrix.md`,
- shortened the top-level README status summary and linked to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- documented a proposed v0.2.x closing plan and narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

No private archive migration is required.

This release adds no archive product CLI, MCP, or service behavior. It does not add provider calls, real ZET transport, shared-update writes, receiver-side renewal writes, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.55` To `v0.2.56`

This is a compatible read-only ZET shared update record review preview patch.

What changed:

- added CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_preview`,
- added `wom-kit/docs/zet-shared-update-record-review-preview.md`,
- updated version metadata to `0.2.56`.

No private archive migration is required.

The new command reads only one archive-relative JSON record and writes nothing. It blocks unsafe record paths, body-included records, token/secret-like values, local absolute path leakage, and true mutation/write/transport/provider/trust flags. It does not add shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.54` To `v0.2.55`

This is a compatible ZET shared update record baseline documentation/example patch.

What changed:

- added `wom-kit/docs/zet-shared-update-record-baseline.md`,
- added a sanitized non-executable example at `wom-kit/examples/zet-shared-update-record/shared-update.example.json`,
- updated version metadata to `0.2.55`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.53` To `v0.2.54`

This is a compatible main branch protection readiness documentation patch.

What changed:

- added `wom-kit/docs/main-branch-protection-readiness.md`,
- documented a staged path from local release gate to future GitHub Actions, required status checks, and optional review requirements,
- updated version metadata to `0.2.54`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add GitHub Actions, enable branch protection, change repository settings, call GitHub APIs, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.52` To `v0.2.53`

This is a compatible release readiness gate patch.

What changed:

- added `wom-kit/tools/check_release_readiness.py`,
- added tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documented the gate at `wom-kit/docs/release-readiness-gate.md`,
- updated version metadata to `0.2.53`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The gate is local-only and read-only. It runs the public link, Korean product-language, and public privacy hygiene checkers only. It does not rewrite files, fetch external URLs, call GitHub APIs, add GitHub Actions, enable branch protection, run product doctors/tests, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.51` To `v0.2.52`

This is a compatible public privacy hygiene checker patch.

What changed:

- added `wom-kit/tools/check_public_privacy.py`,
- added tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholders, and network-free checker scope,
- documented the checker at `wom-kit/docs/public-privacy-hygiene.md`,
- updated version metadata to `0.2.52`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The checker is local-only and read-only. It does not rewrite files, fetch external URLs, call providers, inspect private archives, edit GitHub Releases, scan the whole disk, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.50` To `v0.2.51`

This is a compatible Korean product-language hygiene checker patch.

What changed:

- added `wom-kit/tools/check_korean_product_language.py`,
- added tests for required baseline anchors and high-risk wording drift,
- documented the checker at `wom-kit/docs/korean-product-language-hygiene.md`,
- updated version metadata to `0.2.51`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The checker is local-only and read-only. It does not rewrite files, rename implementation identifiers, fetch external URLs, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.49` To `v0.2.50`

This is a compatible Korean product-language baseline patch.

What changed:

- added `wom-kit/docs/concepts/korean-product-language-baseline.ko.md`,
- documented Korean explanation terms for WOM, zettel-kasten, zet, ZET, objet, lifecycle verbs, block/header/body wording, foreign block safety terms, sharing forms/methods, surface/action terms, SNS-type ZET actions, and messenger-type ZET threads,
- linked the new baseline from README files and public documentation maps,
- updated version metadata to `0.2.50`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not rename CLI commands, JSON fields, schema fields, filenames, or implementation identifiers. It does not implement real ZET transport, real trust/import/acceptance/anchor, attestation/signature writes, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection writes or receipts, recommendation fetching/ranking/feed updates, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.48` To `v0.2.49`

This is a compatible public release link hygiene patch.

What changed:

- added `wom-kit/tools/check_public_links.py`,
- added tests for repo-local Markdown link resolution and GitHub Release body link hygiene,
- documented the difference between repo-local Markdown links and GitHub Release body links,
- converted known unsafe release-note relative file links to absolute GitHub `blob` URLs.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not edit GitHub Releases, fetch external URLs, call providers, publish to WordPress, write projection records or receipts, run ZET transport, fetch or rank recommendations, update neighbor feeds, create trust/import/acceptance/attestation/signature/minting changes, add background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.47` To `v0.2.48`

This is a compatible ZET radio-frequency recommendation model baseline patch.

What changed:

- documented the distinction between followed/neighbor feeds and recommended/broadcast feeds,
- documented the radio-frequency metaphor for user/node-selected ZET channels, scopes, or broadcast lanes,
- documented prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles rather than only LLM prompts,
- added a sanitized non-executable selector example.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not fetch recommendations, rank feeds, update neighbor feeds, call providers, publish to WordPress, write projection records or receipts, run real ZET transport, create trust/import/acceptance/attestation/signature/minting changes, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.46` To `v0.2.47`

This is a compatible ZET closed sharing model baseline patch.

What changed:

- documented the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documented the unit layer distinction between `zet` and `objet`,
- documented the future ZET closed sharing/SNS layer above the base system,
- clarified that GitHub is not the whole ZET sharing architecture,
- clarified that WordPress is one possible user-selected projection surface, not the WOM/ZET UI,
- added sanitized non-executable closed sharing examples.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, write projection records or projection receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, introduce Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.45` To `v0.2.46`

This is a compatible ZET projection plan dry-run preview patch.

What changed:

- added `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- added read-only MCP `zet_projection_plan_check`,
- added metadata-only planning output for one local zet and one operator-declared surface kind,
- added closed safety flags for provider calls, WordPress publishing, projection writes, projection receipts, trust/import/acceptance, attestation, signature, minting, ZET transport, and full-auto behavior.

No private archive migration is required.

The preview reads one local archive zet only enough to confirm existence and extract safe metadata. It does not output the full zet body, write files, create receipts, call providers, publish to WordPress, mint, trust, import, accept, attest, sign, anchor, apply, or run ZET transport.

## From `v0.2.44` To `v0.2.45`

This is a compatible ZET publication surface baseline patch.

What changed:

- added documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- added sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- clarified that posting is not minting,
- clarified that a surface locator is not the canonical zet identity.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## From `v0.2.43` To `v0.2.44`

This is a compatible foreign block attestation statement draft decision preview patch.

What changed:

- added `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- added route previews for keeping a draft under review, revising it, rejecting it later, preparing a future explicit attestation statement review, or requesting more review.

No private archive migration is required.

The preview revalidates the current statement draft review index, statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt. It writes nothing and records no decision. Review notes are local preview context only; raw note bodies are not echoed or stored. Statement drafts remain untrusted and do not create trust, import, acceptance, attestation, signature, mint, receipt write, WordPress publishing, provider calls, sharing, or ZET transport.

## From `v0.2.42` To `v0.2.43`

This is a compatible foreign block attestation statement draft review index patch.

What changed:

- added `archive attestation-statement-draft-review <archive-root> --format json`,
- added optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- added consistency checks for recorded statement draft records, statement draft receipts, current candidate records/receipts, quarantine cases/receipts, and decision records/receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. `--statement-style` and `--review-scope` filter displayed records only; they do not hide blockers from other discovered records. `--case-id` intentionally scopes the verdict to that one case. Indexed statement drafts remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.41` To `v0.2.42`

This is a compatible foreign block attestation statement draft write approval patch.

What changed:

- added `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <safe-actor-id>` to record the statement draft and matching receipt,
- added read-only MCP `record_attestation_statement_draft_check`,
- added stale/tamper checks that revalidate the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before writing.

No private archive migration is required.

Dry-run writes nothing. Approved mode writes exactly two local files and keeps the foreign block untrusted. It does not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.40` To `v0.2.41`

This is a compatible foreign block attestation statement draft preview patch.

What changed:

- added `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_preview`,
- added non-binding statement draft output for one recorded attestation review candidate.

No private archive migration is required.

The preview re-reads current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt state before returning a draft. It writes nothing and does not create trust, import, attestation, signature, mint, receipt, sharing, provider calls, or ZET transport.

## From `v0.2.39` To `v0.2.40`

This is a compatible foreign block attestation review candidate index patch.

What changed:

- added `archive attestation-candidate-review <archive-root> --format json`,
- added optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_review_candidate_index`,
- added consistency checks for recorded candidate records, candidate receipts, current quarantine cases, original quarantine receipts, recorded decisions, and decision receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. Filters only affect displayed candidates; all discovered records are still validated before top-level `ok` is set. Indexed candidates remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.38` To `v0.2.39`

This is a compatible foreign block attestation review candidate write approval patch.

What changed:

- added `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <actor-id>` for recording an untrusted candidate record and receipt,
- added optional `--expected-case-id`, `--expected-review-scope`, `--expected-attestor`, and `--review-note`,
- added read-only MCP `record_attestation_review_candidate_check`.

No private archive migration is required.

Dry-run writes nothing. Approved CLI mode writes exactly two archive-relative files: one candidate record and one receipt. The candidate remains untrusted and does not create an attestation, signature, import, mint, share, provider call, ZET transport, or acceptance.

## From `v0.2.37` To `v0.2.38`

This is a compatible foreign block attestation review candidate planning patch.

What changed:

- added `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_review_candidate_plan`,
- added a safe candidate packet for human review when the recorded decision is `eligible_for_attestation_review`.

No private archive migration is required.

The candidate planner reads only sanitized quarantine case, quarantine receipt, decision record, and decision receipt metadata. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, call providers, or run ZET transport.

`prepare_attestation_review_candidate` is still not an attestation. It only means a human can review a candidate packet before any future explicit attestation workflow exists.

## From `v0.2.36` To `v0.2.37`

This is a compatible foreign block decision outcome planning patch.

What changed:

- added `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--reviewer`, and `--review-note`,
- added read-only MCP `foreign_block_decision_outcome_plan`,
- added conservative next-step routing for recorded decisions.

No private archive migration is required.

The outcome planner reads only the current quarantine case, original quarantine receipt, recorded quarantine decision, and decision receipt. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

`eligible_for_attestation_review` is still not trust. It only maps to `prepare_attestation_review_candidate` for a future explicit workflow.

## From `v0.2.35` To `v0.2.36`

This is a compatible foreign block quarantine decision review index patch.

What changed:

- added `archive quarantine-decision-review <archive-root> --format json`,
- added optional `--case-id`, `--decision`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_decision_review_index`,
- added consistency checks for recorded quarantine decision records and matching decision receipts.

No private archive migration is required.

The review index reads only quarantine cases, original quarantine receipts, recorded quarantine decision JSON, and matching decision receipts. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

## From `v0.2.34` To `v0.2.35`

This is a compatible foreign block quarantine decision write approval patch.

What changed:

- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- added optional `--expected-case-id`, `--expected-decision`, and `--review-note`,
- added read-only MCP `record_quarantine_decision_check`,
- added replay validation that re-reads the current quarantine case and matching quarantine write receipt before any approved local decision record write.

No private archive migration is required.

The approved write creates exactly two local files:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

This records an operator-reviewed quarantine decision only. It does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, execute it, accept it, apply it, share it, or call providers.

MCP remains read-only for this workflow. Real quarantine decision recording is CLI-only and requires `--approve --reviewed-by`.

## From `v0.2.33` To `v0.2.34`

This is a compatible foreign block quarantine decision preview patch.

What changed:

- added `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, and `--review-note` preview context,
- added read-only MCP `foreign_block_quarantine_decision_check`,
- added a decision aid for existing untrusted quarantine cases.

No private archive migration is required.

Quarantine decision preview reads one existing quarantine case and matching receipt. It does not write a decision, record approval, trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, or call providers.

The preview may propose:

- `keep_quarantined`,
- `reject_and_keep_record`,
- `eligible_for_attestation_review`,
- `needs_more_review`.

`eligible_for_attestation_review` is still not trust. It only means a future explicit attestation review path may be appropriate.

## From `v0.2.32` To `v0.2.33`

This is a compatible foreign block quarantine review index patch.

What changed:

- added `archive quarantine-review <archive-root> --format json`,
- added optional `--case-id`, `--status`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_review_index`,
- added read-only inventory and consistency checks for existing untrusted quarantine cases and matching quarantine write receipts.

No private archive migration is required.

Quarantine review index reads existing files only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Indexing a case does not mean the case is trusted, imported, accepted, attested, minted, anchored, delegated, signed, or safe to apply. It only gives a reviewer a stable list of untrusted quarantine cases and obvious consistency blockers/warnings.

## From `v0.2.31` To `v0.2.32`

This is a compatible foreign block quarantine write approval patch.

What changed:

- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- added read-only MCP `quarantine_foreign_block_check`,
- added a CLI-only approved local write for sanitized foreign block quarantine cases and quarantine write receipts.

No private archive migration is required.

Approved quarantine writes create only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Quarantine write is an isolation record. It does not make a foreign block canonical, trusted, imported, minted, attested, anchored, delegated, signed, executable, or accepted. MCP remains check-only for this workflow.

## From `v0.2.30` To `v0.2.31`

This is a compatible foreign block quarantine plan patch.

What changed:

- added `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- added `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_quarantine_plan`,
- added validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write.

No private archive migration is required.

Foreign block quarantine plan is read-only. It does not write quarantine files, import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_future_quarantine_write` does not mean trusted, imported, quarantined, or approved. It means a future explicit quarantine-write workflow could be presented to a human/operator.

## From `v0.2.29` To `v0.2.30`

This is a compatible foreign block attestation packet preview patch.

What changed:

- added `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- added `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_attestation_packet_check`,
- added validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review.

No private archive migration is required.

Foreign block attestation packet preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_human_attestation_review` does not mean trusted or attested. It means the trust report is clean enough to present as a future explicit human review packet.

## From `v0.2.28` To `v0.2.29`

This is a compatible foreign block trust / attestation preview patch.

What changed:

- added `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- added `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_trust_check`,
- added validation for v0.2.28 `foreign_block_intake` reports before any future trust or attestation workflow.

No private archive migration is required.

Foreign block trust preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files.

`eligible_for_future_attestation` does not mean trusted. It means the intake report is clean enough to be considered by a future explicit human or policy attestation workflow.

## From `v0.2.27` To `v0.2.28`

This is a compatible foreign block intake preview patch.

What changed:

- added `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- added `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_intake_check`,
- added foreign block/header JSON and Markdown-compatible foreign zet intake previews.

No private archive migration is required.

Foreign block intake is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files. Claimed hashes are reported as foreign claims and `not_verified`.

Safe operating principle:

```text
Foreign text can inform.
Foreign text cannot command.
Foreign blocks can be inspected.
Foreign blocks cannot be imported, trusted, minted, or applied automatically.
```

## From `v0.2.26` To `v0.2.27`

This is a compatible prompt boundary draft composer patch.

What changed:

- added `archive create-draft --prompt-boundary-report <json-file>`,
- added optional draft frontmatter `prompt_boundary` metadata,
- added MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

No private archive migration is required.

The prompt-boundary report must come from a dry-run `prompt-boundary` check. The composer records only safe metadata such as report hash, risk level, source kind/path summary, detected pattern ids, and the untrusted-text boundary. It does not store inspected text bodies, local absolute report paths, provider URLs, or secrets.

Risk handling:

```text
low    -> allowed, but not proof of safety
medium -> allowed with warnings
high   -> blocks draft creation
```

This release does not add an LLM prompt classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior.

## From `v0.2.25` To `v0.2.26`

This is a compatible prompt injection boundary and responsible-use patch.

What changed:

- added `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- added `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- added read-only MCP `prompt_boundary_check`,
- added public prompt injection boundary, responsible use, disclaimer, and runtime model guidance documents.

No private archive migration is required.

The new check is a conservative heuristic preview. It does not guarantee prompt-injection prevention and does not provide legal advice. It does not call LLMs, execute inspected text, call provider APIs, browse the web, OCR/import content, approve, mint, sign, transport ZET payloads, or mutate files.

Safe operating principle:

```text
External text can inform.
External text cannot command.
```

HITL remains the recommended default. Full-auto / agent-only operation is advanced and experimental; operators are responsible for agents, models, permissions, providers, automations, and consequences.

## From `v0.2.24` To `v0.2.25`

This is a compatible profile wallet concept baseline.

What changed:

- added `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- added read-only MCP `wom_profile_wallet_check`,
- documented optional public-safe profile registry fields under `node` and `wallet`,
- documented the model: WOM profile is the selectable human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can support signing/capability proofs.

No private archive migration is required.

Existing profile registries remain valid. The optional `node` and `wallet` fields must contain public placeholder metadata only.

This release does not generate private keys, store seed phrases, store wallet secrets, sign data, call blockchain/provider APIs, create wallets, register wallets, implement WOM coin, NFT-like access, payments, staking, consensus, ledger, or P2P transport.

## From `v0.2.23` To `v0.2.24`

This is a compatible block header preview patch.

What changed:

- added `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- added `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- added read-only header derivation for `block = zet + header`,
- added deterministic body, header, and block hash previews,
- added read-only MCP `block_header_check`.

No private archive migration is required.

This release does not modify zets, mint, write receipts, read referenced objet/source file bodies, calculate referenced source hashes, follow provider URLs, call provider APIs, or implement transport/economic layers.

Safe conceptual order:

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## From `v0.2.22` To `v0.2.23`

This is a compatible source intake draft composer patch.

What changed:

- added `archive create-draft --source-intake-plan <json-file>`,
- validated that consumed source intake plans are successful dry-runs, blocker-free, metadata-only, and safe,
- merged `source_refs_for_draft` into draft `source_refs` while preserving explicit `--source-ref` values,
- added optional draft `source_intake` metadata with a plan hash and content access proof,
- added MCP `create_draft_zettel` support for structured `source_intake_plan` objects.

No private archive migration is required.

This release does not read original source files from the plan, follow local paths inside the plan, apply source intake, capture objets, copy, upload, import, OCR, transcribe, calculate full source hashes, call provider APIs, automatically mint, or add MCP real minting.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json > source-intake-plan.json

archive create-draft <archive-root> --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

## From `v0.2.21` To `v0.2.22`

This is a compatible source intake planner patch.

What changed:

- added `archive source-intake <archive-root> --dry-run --format json`,
- added metadata-only locator planning for local files, source map items, source-relative paths, manifested objets, provider refs, and AI artifacts,
- added draft-ready `source_refs_for_draft` so AI runtimes can feed safe refs into `create-draft --dry-run`,
- added object storage context reporting from `provider-bindings.yml`,
- added read-only MCP `source_intake_plan`.

No private archive migration is required.

This release does not read file bodies, calculate full hashes, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts automatically, mint, or sync providers.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json
```

## From `v0.2.20` To `v0.2.21`

This is a compatible object storage/objet setup planner patch.

What changed:

- added `archive object-storage <archive-root> --dry-run --format json`,
- added safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- added default objet prefix planning as `archives/<archive_id>/objets/`,
- added strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- v0.2 historically allowed reviewed local provider-metadata and setup-receipt writes; in v0.4.0 GitHub setup approval is fixed closed before private profile/archive reads and writes nothing,
- added optional ignored local object storage account hints with `--write-local-profile`,
- added read-only MCP `object_storage_setup_plan`.

No private archive migration is required.

This release does not create buckets, run OAuth, call provider APIs, upload, sync, copy source files, hash files, or import source content.

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --storage-account-ref storage:account:honggildong \
  --format json
```

## From `v0.2.19` To `v0.2.20`

This is a compatible GitHub profile repository setup planner patch.

What changed:

- added `archive github-repo <archive-root> --dry-run --format json`,
- added safe default repository names as `zettel-kasten-<profile_slug>`,
- added strict safety gates for profile slugs, repository names, GitHub owners, and account references,
- added `--approve --reviewed-by` for local-only provider metadata and setup receipt writes,
- added optional ignored local account hints with `--write-local-profile`,
- added read-only MCP `github_repository_setup_plan`.

No private archive migration is required.

This release does not create GitHub repositories, run OAuth, call GitHub APIs, run `gh`, configure git remotes, push, or sync.

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

## From `v0.2.18` To `v0.2.19`

This is a compatible WOM-kit naming and path cleanup patch.

What changed:

- the implementation folder is now `wom-kit/`,
- the Python import package is now `wom_kit`,
- package metadata now uses the project name `wom-kit`,
- `archive` and `archive-mcp` remain available as compatibility console scripts,
- preferred aliases `wom` and `wom-mcp` are available when installed from the package metadata.

No private archive migration is required.

Current source-development commands use the import package. Since v0.3.291,
the direct wrapper is reserved for a verified bridge or pristine recovery:

```bash
PYTHONPATH=wom-kit/src python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

## From `v0.2.17` To `v0.2.18`

This is a compatible profile-aware draft zet creation dry-run patch.

What changed:

- added `archive create-draft --dry-run --format json`,
- added replay-safe draft creation fields for draft id, created-at timestamp, expected body hash, and draft approver,
- added profile-aware provenance fields for resolved profile id, operator id, authority mode, source refs, local AI sessions, assisting actors, and supervising actors,
- extended MCP `create_draft_zettel` with the same dry-run and profile-aware inputs,
- kept real draft writes constrained to `inbox/`,
- kept minting separate through `mint-zet --approve --reviewed-by`.

No private archive migration is required. Existing drafts remain valid.

For profile-bound AI writes, first run profile resolution and runtime context, then dry-run draft creation. After human draft approval, replay the same draft id, created-at timestamp, expected archive id/type, profile id, and expected body hash.

```bash
git fetch --tags
git checkout v0.2.18
```

## From `v0.2.16` To `v0.2.17`

This is a compatible WOM Profile Registry dry-run patch.

What changed:

- added `archive profile-list --registry <path> --format json`,
- added `archive profile-resolve --registry <path> --target <query> --format json`,
- added read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- added token-state aware profile resolution before runtime context and draft work,
- added an example registry template at `wom-kit/templates/profiles/wom-profiles.example.yml`.

No private archive migration is required.

This release does not add profile registration, token storage, create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

```bash
git fetch --tags
git checkout v0.2.17
```

## From `v0.2.15` To `v0.2.16`

This is a compatible WOM AI Runtime Context Layer patch.

What changed:

- added `archive runtime-context <archive-root> --format json`,
- added `--expected-archive-id`, `--expected-type`, and `--strict` checks so terminal-capable AI runtimes can confirm they are operating on the intended archive before creating drafts, running dry-runs, or asking for mint approval,
- added default local path redaction; JSON paths are archive-relative unless `--no-redact-local-paths` is explicitly used for trusted local debugging,
- added read-only MCP tool `archive_runtime_context` with existing MCP allowed-root enforcement.

No private archive migration is required.

This release does not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP apply tool.

```bash
git fetch --tags
git checkout v0.2.16
```

## From `v0.2.14` To `v0.2.15`

This is a compatible WOM Safe HTML Profile validator dry-run patch.

What changed:

- added `archive check-safe-html --path <zet> --dry-run` as a read-only CLI command that previews whether a v0.2 Markdown-compatible zet is compatible with a future WOM Safe HTML Profile migration,
- the validator blocks zet bodies that contain `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, or inline event handler attributes such as `onclick=`,
- the validator returns structured JSON with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, a profile allowlist, a UI, live sharing, P2P transport, or external provider sync. Existing Markdown-compatible zets remain valid.

```bash
git fetch --tags
git checkout v0.2.15
```

## From `v0.2.13` To `v0.2.14`

This is a compatible documentation/spec baseline patch for the WOM Safe HTML Profile.

What changed:

- documented the distinction between `WOM`, `zet`, and `ZET`,
- clarified that `zet` is the unit document minted inside a zettel-kasten,
- clarified that `ZET` is the future communication layer that can become messenger, SNS/feed, or collaboration,
- documented WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- kept Markdown as the v0.2 authoring/import compatibility format.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, or external provider sync.

```bash
git fetch --tags
git checkout v0.2.14
```

## From `v0.2.12` To `v0.2.13`

This is a compatible WOM naming baseline and CLI alias patch.

What changed:

- documented `WOM` as the umbrella name and `Widesider of Modernity` as its expansion,
- added `archive mint-zet` as the preferred command name for minting a zet,
- kept `archive mint-zettel` as a compatibility alias,
- v0.2 historically added `archive parcel` as the preferred command name for a bounded portable unit; in v0.4.0 the command is fixed closed before private view/body/manifest reads and creates no workpack,
- kept `archive pack` as a compatibility alias with the same v0.4.0 fixed-close boundary,
- added `archive admit --dry-run` as the preferred command name for previewing parcel/workpack admission,
- kept `archive import --dry-run` as a compatibility alias.

No private archive migration is required.

Existing scripts can keep using the old names, but new user-facing docs should prefer `mint-zet`, `parcel`, and `admit`.

```bash
git fetch --tags
git checkout v0.2.13
```

## From `v0.2.11` To `v0.2.12`

This is a compatible real delegate receipt write patch.

What changed:

- added `archive delegate-zet --approve --reviewed-by <actor>`,
- real delegate writes create `receipts/delegate/*.delegate.json`,
- `archive doctor` validates applied delegate receipts,
- real delegate capability receipts get a generated nonce,
- claim/spent/revocation registries remain explicitly unimplemented.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.12
```

## From `v0.2.10` To `v0.2.11`

This is a compatible delegate capability contract patch.

What changed:

- added `--target-policy counterparty_bound|claimable_once` to `archive delegate-zet --dry-run`,
- made `--target-archive` optional for `claimable_once` delegate previews,
- added `delegation_capability`, `claim_binding`, and `settlement_condition` preview fields,
- kept settlement non-financial with `mode: "none"`,
- kept real P2P, claim registry, spent registry, revocation, blockchain, and payment unavailable.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.11
```

## From `v0.2.9` To `v0.2.10`

This is a compatible dry-run lifecycle feature patch.

What changed:

- added `archive delegate-zet --dry-run`,
- added `archive attest-zet --dry-run`,
- added `archive anchor-zet --dry-run`,
- added read-only MCP checks for delegate, attest, and anchor,
- added schemas for delegate receipts, attestation receipts, and anchor metadata.

No private archive migration is required.

Real P2P, feed, transport, external sending, and foreign zet import remain unavailable.

```bash
git fetch --tags
git checkout v0.2.10
```

## From `v0.2.8` To `v0.2.9`

This is a compatible terminology stabilization patch.

What changed:

- new archives default to `human_minting`,
- existing `human_promotion` archives remain valid,
- `minting_rules` may be used in zettel rules,
- `promotion_rules` remains available as the v0.2 legacy fallback,
- user-facing docs now prefer minting language.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.9
```

## From `v0.2.7` To `v0.2.8`

This is a compatible minting lifecycle feature patch.

What changed:

- added `archive mint-zettel --dry-run`,
- added `archive mint-zettel --approve --reviewed-by <id>`,
- added mint receipts under `receipts/mint/`,
- added draft snapshots under `receipts/mint/drafts/`,
- added canonical zettel `mint` frontmatter,
- added doctor validation for mint receipts and SHA-256 file links,
- added read-only MCP `mint_zettel_check`.

No private archive migration is required.

If you mint new zettels, keep the generated canonical zettel, mint receipt, and draft snapshot together.

```bash
git fetch --tags
git checkout v0.2.8
```

## From `v0.2.3` To `v0.2.4`

This is a documentation polish patch.

What changed:

- rewrote `README.md` as a cleaner English project entrypoint,
- added `README.ko.md` as a full Korean entrypoint,
- split upgrade documentation into English and Korean files,
- clarified the public positioning, current status, privacy boundary, storage model, and text provenance.

No private archive migration is required.

Recommended steps:

```bash
git fetch --tags
git checkout v0.2.4
```

## From `v0.2.2` To `v0.2.3`

This is a bilingual documentation patch.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.3
```

## From `v0.2.1` To `v0.2.2`

This is a documentation, provenance, and public-history hygiene patch.

No private archive migration is required.

Important concept change:

```text
original editable text != OCR/AI-derived text
```

Both should be stored, but OCR/AI-derived text should keep derivation metadata and review status.

## Staying On An Older Version

Users may stay on an older version.

That is part of the design:

```text
old version -> old rule set
new version -> updated rule set
```

Future sharing and collaboration features should make the sender/receiver version explicit.

## Future Release Requirements

Every future public release should include:

- changelog entry,
- release note under `wom-kit/docs/releases/`,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
