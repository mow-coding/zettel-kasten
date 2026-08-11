# 2026-08-11 v0.3.314 Letter 126 long-operation and private-index recovery

## Chronology

The user first asked for a candid product assessment grounded in accumulated
real-use feedback, while correcting two framing errors: popularity is not proof
that an LLM wiki or second brain works, and the lack of a standalone GUI is not
itself a v0.3.x defect because Codex and Claude Desktop are the intended user
interface. The assessment was completed conceptually but not yet returned when
Letter 126 arrived. The user asked that the evaluation be retained and that the
new field report be incorporated into implementation work.

The exact protected-client-archive letter was read from
`archive/ops/feedback/letters/wom-feedback-20260811-126.md`. The source letter
and real archive remained read-only. Only its two explicitly named, content-free
scratch diagnostic JSON files and the generated SQLite header/sidecar presence
were inspected.

## Letter 126 field evidence

- `project-version-update` v0.3.310 to v0.3.313 preview took about 29.5 seconds.
- approval outlived the external caller's 124-second limit, continued for about
  15 minutes, and eventually aligned source, pin, and receipt and removed its
  lock;
- `archive index` took 3 minutes 4 seconds and reported a current complete index
  for 8,601 zettels, 23,521 objects, 3,750 derived texts, 2,634 edges, and
  121,765 facets;
- `archive index-health` took 2 minutes 1 second and returned exit 1 even though
  the public live/indexed counts matched and every public difference count was
  zero;
- the sole reason was `private_objet_metadata_projection_unavailable`; the
  nested private state was blocked, while top-level blockers were empty and the
  only next action incorrectly claimed the generated index matched.

The user asked for bounded Git verification, durable status/checkpoint and safe
wait/cancel/recovery behavior, a supported private-projection recovery route,
honest top-level blockers/actions, and an exact client sequence through final
mint review.

## Confirmed root causes

### Per-entry Git process fan-out

The updater's tree loader launches `git cat-file -s` and a separate `git
cat-file blob` process for every tracked path. Target and current trees are
loaded during planning and again during approval. For the observed v0.3.310 and
v0.3.313 tree sizes, this is over eleven thousand Git child launches on Windows.
Existing documentation already claimed unique-object batch materialization, so
the implementation did not match the public contract.

### Self-defeating WAL health contract

Ordinary `archive index` already compiles the private objet metadata authority
and installs its four generated private tables in the same SQLite transaction as
the public index. No new private authority writer is required.

The writer persists WAL mode. After the final connection closes, SQLite can
checkpoint and remove `-wal` and `-shm` while the main database header remains
WAL (`2/2`). The private read preflight nevertheless requires both sidecars for
any WAL header and rejects the clean checkpointed state before opening SQLite.
Existing tests explicitly froze that production failure and held an artificial
anchor connection open to make success tests pass.

Relaxing the preflight is not safe: a synthetic `mode=ro` query against a clean
WAL-header database created new WAL/SHM files. That would contradict
`index-health`'s no-write promise. SQLite's documented rollback `DELETE` mode is
therefore the new generated-index persistence boundary; it deletes the rollback
journal after commit and remains compatible with true `mode=ro` inspection.
Every generated-index writer must use the same mode so a later mint delta cannot
reintroduce the defect.

### Diagnostic composition ordering

Public `next_safe_actions` are composed before private health is evaluated. The
private composer changed only ok/state/stale/blocker fields and copied the old
public action unchanged. The closed C1/C2/C6 cases also described a nested
blocked state while mapping the diagnostic only into top-level stale reasons.

## v0.3.314 implementation decisions

1. Use bounded persistent `git cat-file --batch` materialization, validate every
   returned object id, type, size, frame, byte count, and digest, and fetch each
   duplicate object id once per tree.
2. Persist the disposable generated index in rollback `DELETE` mode for rebuild
   and delta writers; health opens the public index with true `mode=ro` and
   proves that it created no sidecars.
3. Promote blocked private cases to fixed top-level blockers and replace the
   misleading action with the ordinary combined rebuild command followed by
   health verification when the authority itself is valid.
4. Add one CLI-only operation-control contract for opted-in long-command output,
   rather than a separate status command per operation. Status and bounded wait
   are read-only. v0.3.314 reports `cancel_supported: false` and fixed
   `operation_cancel_not_supported`; no cooperative cancellation request is
   implemented. Recovery planning is read-only and never deletes a lock.
5. Do not claim true forward resume. `resume_supported` remains false; a proved
   rollback leads to a fresh preview and replay, while uncertain state remains a
   recovery hold.
6. Do not add an MCP cancellation writer, daemon, queue, Redis dependency,
   hidden WAL anchor, or automatic protected-client-archive mutation.

## Product-evaluation consequence

Letter 126 strengthens the earlier criticism in a concrete way. WOM's field
feedback loop is real and valuable, but its frontier-host UX still fails when a
correct operation outlives the host transport and the model cannot query durable
state. It also shows why correctness must be consolidated into shared
invariants: a private-index safety contract that looked strict in tests made the
ordinary real workflow impossible. The proper response is fewer shared
contracts (bounded batch I/O, one journal mode, and one operation-control
surface), not another pile of unrelated special commands.

## Review correction: pre-open storage boundary

The first focused patch made generated writers use `DELETE` and public health
use URI `mode=ro`. A direct reviewer reproduction then found that this was still
insufficient: public health opened an old clean WAL-header database before the
private preflight, SQLite created `-wal` and `-shm`, and the later private check
incorrectly returned current. That contradicted `privacy_guards.writes: false`
and bypassed the advertised migration.

The corrected contract is pre-open and shared. Normal reads accept only a valid
SQLite `1/1` header with no WAL, SHM, or rollback-journal path. Legacy WAL,
recovery residue, and unsafe path identity block before any SQLite connection.
When that preflight blocks, public index comparison is recorded as not performed
and no missing/extra-row claim is synthesized. The nested private C6 blocker and
the exact ordinary rebuild-then-health commands remain visible at top level.

Existing-path incremental writers pass the same clean-DELETE preflight before
opening, so they cannot silently migrate or mutate an old WAL database. Only the
explicit full `archive index` rebuild performs the disposable projection
conversion. Focused tests preserve database bytes, logical row counts, and
sidecar absence across a rejected incremental open.

The preflight was tightened again to read the bounded header through an OS file
descriptor and compare lstat/fstat identity before and after the read. A normal
internal DELETE writer leaves a rollback journal, so concurrent health blocks
before another SQLite connection and does not change database or journal
identity. This is not an OS-wide lock; an unmanaged external writer can still
race in the narrow interval after preflight, so conclusive health requires a
quiescent generated index and the final private identity check remains the
fail-closed backstop.

The cheap storage preflight now runs before live-zettel enumeration. A known
legacy WAL, invalid header, or recovery sidecar therefore returns the fixed
rebuild route without repeating the Letter 126 two-minute archive scan. The
result explicitly sets both `live_zettel_enumeration_performed` and
`index_comparison_performed` to false.

## User philosophy clarification

The user strongly corrected the assistant's comparison language. This was not
a missing product philosophy discovered on 2026-08-11. The accepted 2026-07-15
design had already made the distinction precisely: a Palantir-style enterprise
ontology maps stable real-world entities into an operational world model,
whereas WOM refuses to make a stable/global entity map the primary truth about
human memory. For the same subject, changes and contradictions in a person's
perception remain preserved as time-ordered artifacts.

The assistant's product evaluation had incorrectly compressed that specific
design into generic “artifact-first” language and then treated the sharper
distinction as absent. The correction restores the existing decision; it does
not invent a new philosophy or authorize an entity resolver, schema migration,
graph writer, UI change, or automatic interpretation.

## Verification boundary

Development and tests use temporary repositories and archives only. The real
protected client archive is not reindexed, repaired, minted, or otherwise written during
implementation. A final reviewed client sequence will be returned only after
focused tests, independent review, full regression, package-resource sync, and
release-artifact verification are complete.

## Release closeout

PR #58 passed all required GitHub Actions checks and was squash-merged into
`main` as `f0f7794554019303cc249e5fd7c36e0d93e90aaf`. Independent source,
security, release-documentation, and package audits closed with no open P0,
P1, or P2 finding. The frozen local regression evidence included 1,375 CLI
tests and 1,373 explicitly selected non-CLI tests; both suites completed with
no failure or error.

The annotated tag `v0.3.314` resolves to that exact merge commit. The main-push
CI run `31473640874` and tag-push CI run `31474162504` both passed. The GitHub
Release is published as a non-draft, non-prerelease release at
<https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.314>.

The exact release asset is
`wom_kit-0.3.314-py3-none-any.whl`, 1,764,457 bytes, with SHA-256
`034f65cdb0bda1b9236bd0f27637211cb4626d985b67f8a0e712e687b5833439`.
The merged-commit wheel check verified version `0.3.314`, all 145 packaged
resources, all four console entry points, the runtime-skill lifecycle, and
strict Doctor behavior. Both MCP aliases exposed 121 tools and produced the
same 102,829-byte canonical inventory with SHA-256
`931dc2bd42037c41b3bb2bb05b04dec5b4b4c58ebf384b57deb6420ef2d8be98`.

An independent anonymous check downloaded the public asset without GitHub API
authentication or custom request headers and received HTTP 200. Its byte count
and SHA-256 matched the verified local wheel. A new Python 3.12 environment
installed that downloaded wheel with dependencies, passed `pip check`, imported
`wom_kit` at version `0.3.314`, returned version `0.3.314` through both CLI
aliases, and repeated the two-alias MCP inventory equality check.

No protected client archive, credential store, external provider, canonical
zettel, or private source was read or written for this release closeout. The
release proves the public artifact and synthetic/temporary validation boundary;
real-archive upgrade execution and human acceptance remain separate evidence.
