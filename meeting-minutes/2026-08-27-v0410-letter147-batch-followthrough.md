# Meeting Minutes: v0.4.10 Letter 147 Batch Follow-through

Date: 2026-08-27

## Scope correction

The user clarified that Letter 146 came from a client that had not installed
the release it was supposed to test. The user will ask that client to install
v0.4.9 and retest. This release therefore does not treat Letter 146 as new
v0.4.10 implementation evidence and does not change behavior solely from that
report. The report remains preserved for later comparison.

Letter 147 remains the confirmed follow-through scope. v0.4.9 made the exact
single-file path usable, but ordinary multi-item intake and capture still
required an impractical repetition of human decisions or remained closed.

## Human decision boundary

The agreed v0.4.10 pipeline uses two important human decisions regardless of
whether the batch contains one item or the maximum 1,000 items:

1. Approve the plainly described complete intake batch.
2. Approve capture of the exact local bytes produced by that intake evidence.

WOM, not the person, derives and verifies item counts, exact target paths,
source hashes, receipt bytes, archive identity, drift, checkpoints, and final
completion evidence. Public output stays content-free. A person is never asked
to count archive rows, compare digests, or reconstruct a private receipt path.

## Implemented execution shape

- `source-intake-batch` writes 1–1,000 canonical intake receipts and one
  generated Objet-capture request under one `ExactOperationManifest v1`.
- Every source in this two-decision route must be archive-relative. An external
  or mixed batch cannot generate the promised capture handoff and therefore
  fails before approval; the v0.4.9 single-file external metadata route remains
  unchanged.
- The intake phase supports item checkpoints and same-authenticated-claim
  resume for the exact unchanged operation. The ordinary resume command needs
  only the unchanged manifest and same reviewer; WOM discovers one authenticated
  candidate and never makes the person reconstruct internal ids.
- The capture phase receives the completed intake execution SHA-256 and derives
  the request path instead of asking the operator to copy or edit it.
- Capture authority requires the authenticated succeeded approval claim,
  checkpoint chain, final result receipt, current intake receipts, current
  staged bytes, and the same archive identity. An unkeyed self-hash alone is
  not completion authority.
- Forged, copied, stale, incomplete, or cross-archive evidence fails before
  capture mutation.
- Separate native operation identities describe intake batch and capture batch
  truthfully and remain bound through the lower writer and final receipt.
- Reconciliation is strictly read-only, both resume routes obey project runtime
  isolation, canonical target publication is create-only, and uncertain
  post-write failures admit that writes may have occurred.

## Interruption decision

The existing capture service performs a bounded whole selection but does not
expose an honest per-item external checkpoint boundary. Wrapping it in a fake
per-item resume contract would overstate recoverability. If capture is
interrupted or only partly converges, WOM requires a fresh exact dry-run against
current state and a new native human decision. Automatic retry and same-claim
capture resume are explicitly false. Existing verified bytes and rows are
reconciled without duplication.

## Performance evidence

Only synthetic archives were used; no client archive was read or written for
the benchmark.

- 508-item plan: 33.994528 seconds.
- 508-item post-decision request reread: 0.012481 seconds.
- 508-item per-item revalidation: 31.504864 seconds.
- 1,000-item plan: 42.925746 seconds.
- 1,000-item post-decision request reread: 0.011020 seconds.
- 1,000-item per-item revalidation: 30.094036 seconds.
- Deterministic reads are one request plus N sources in planning and one
  request plus N sources after the decision. The former quadratic request
  reread is removed.
- CLI status begins before planning, and a content-free background heartbeat is
  bounded to at most 10 seconds of silence.

The remaining cost is repeated per-item Windows path, configuration,
provider-metadata, and manifest reconstruction. That optimization has a
separate v0.4.11 implementation checkpoint and is deliberately excluded from
v0.4.10 release claims. Broader generic exact-operation ancestor-handle
portability and safe create-only publication on filesystems without hard-link
support remain explicit hardening debt; unsupported publication blocks instead
of falling back to overwrite behavior.

## Client and security boundary

The development worktree may change code, tests, public documentation, and
synthetic fixtures only. It must not install v0.4.10 into the client's project,
run the client's actual batch, or write the client archive. After a verified
public release, the client installs it in the project's isolated runtime and
runs the two project-scoped decisions. Public release surfaces contain no
client payload, credential, provider value, private path, or private feedback
body.

## Runtime-integrity regression and correction

The first complete Windows shard exposed a separate runtime-alignment
performance regression. The integrity check launched one `git hash-object`
process for every tracked Python file. The package currently contains 74 such
files, so parallel test load could consume the existing 12-second shared Git
probe budget even though the bytes were valid.

The correction keeps the security boundary and the 12-second budget. It rereads
each tracked file through the existing bounded real-file reader, enforces a
32 MiB per-file and 128 MiB aggregate limit, computes the exact Git blob OID
locally with the repository's SHA-1 or SHA-256 object format, and compares it in
constant time with the clean HEAD inventory. Post-snapshot byte drift remains a
hard failure. The focused regression checks the actual former defect directly:
the full-source bridge must start no per-file `git hash-object --no-filters`
calls, and the shared probe budget must not be exhausted. It does not rely on a
fragile arbitrary total-call threshold.

## Queued approval-target preview requirement

The user asked that native approval prompts identify what will be acted on.
Mint/discard prompts should make the exact zet or draft inspectable, while edge
or link prompts should identify both endpoints, the proposed relationship, and
the evidence for suggesting it. This is explicitly queued after the v0.4.10
release and the newer feedback review; it is not claimed as implemented here.

The surface must follow WOM's established product language rather than generic
file-manager vocabulary. Alphabetic `WOM`, `zet`, `ZET`, and `objet` stay
distinct; `ZET` is the future sharing/communication layer and must not label a
local draft. Korean mint wording begins from the natural phrase `이 zet를
정본으로 발행할까요?`; product-facing sentences are derived from what a
person would actually say; internal CLI names and schema fields remain
technical identifiers. `retire` after a completed publication is `퇴역`, while
discarding an unpublished draft is `폐기`; the UI must not collapse them into
one action. Sensitive titles, paths, body excerpts, and relation evidence may
appear only in an explicitly opened local detail/preview surface and must not be
copied into public logs or ordinary machine-readable output.

## Files and release work

The v0.4.10 release updates package version sources, current README and upgrade
guidance, the public release note, capability and approval documentation,
project-runtime supply lock/policy bindings, the packaged release-note mirror,
and focused release/resource tests. The isolated installed-wheel check drives a
three-file intake through both native decisions and verifies the resulting
bytes and authenticated claims. Historical v0.4.9 release notes remain
unchanged as source history.

## Final release-audit correction

The final independent audit found one failure-reporting mismatch. Native
approval-dialog failures and workflow argument/contract failures occur before
the domain writer is entered, but the first implementation reported them as
if archive writes might have occurred. Source intake also suggested resume even
though no started approval claim could exist.

The correction keeps only `exact_human_approval_state_unknown` in the
post-writer uncertain-outcome category. Pre-writer approval-operation and
writer-contract failures now report zero possible writes and provide no false
resume or capture-reapproval instruction. Focused source/capture JSON and text
tests passed with 44 passed, 1 skipped, and 13 subtests; package resources
remained synchronized at 165/165. No client archive was accessed.

## Pre-release verification evidence

The final local pre-release gate completed without a client install or client
archive mutation:

- Eight focused runtime-alignment and integrity regressions passed, including
  post-snapshot byte drift, origin-key probing, isolated bootstrap, and the
  direct assertion that no per-file `git hash-object --no-filters` fan-out
  remains.
- All seven real project-update hard-exit boundaries recovered from the exact
  next durable stage without redisplaying native approval; the matrix completed
  in 368.127 seconds.
- The formerly transient exact Git-backup staging regression passed alone in
  27.253 seconds.
- Package-resource synchronization passed at 165/165, `git diff --check`
  reported no errors, and the release-readiness link, Korean product-language,
  public-privacy, and runtime-skill gates all passed.
- A new isolated wheel build and install passed all four entrypoints, both MCP
  inventories, the installed v0.4.9 compatibility workflows, and the complete
  installed v0.4.10 three-item two-decision batch flow. All three captured
  object byte sequences matched their sources.
- The wheel contains 244 files and has SHA-256
  `008f998e4f640ee88565d36988eb6e8dbd03c608d538117c6126a35e4ad13fdf`.
  Its privacy scan covered 244 text-like members and 13,646,181 bytes, finding
  zero Windows user-path matches and zero secret-pattern matches.

These are pre-commit local results. Required hosted Ubuntu and Windows CI,
merge-SHA tagging, GitHub Release publication, anonymous artifact download, and
downloaded-wheel re-verification remain release conditions and are not claimed
complete in this checkpoint.
