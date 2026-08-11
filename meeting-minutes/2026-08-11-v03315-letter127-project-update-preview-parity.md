# v0.3.315 Letter 127 project-update preview parity

Date: 2026-08-11

## Incident intake

A protected beta client installed the exact public v0.3.314 wheel and used the
official project-version-update sequence from a clean v0.3.313 source mirror.
The read-only preview completed as `ready_for_approval` with no blocker and
reported zero unexpected worktree entries. The separately approved operation
fetched and verified the release, then blocked before checkout because the
verified target would collide with an ignored or otherwise unsafe filesystem
entry.

The client stopped without deleting or moving any entry, did not repeat the
approved writer, and did not continue to index or mint. Source bytes, installed
version pins, receipts, locks, and updater processes remained at a safe
pre-update state.

Only the exact feedback letter named by the user was read from the protected
client archive. No other protected file, source entry, zettel, object, provider,
or credential store was inspected or changed.

## User correction

The user rejected the prior statement that v0.3.314 was ready for beta use:
an official release that an existing beta client cannot update is not a
complete beta-ready delivery. The assistant accepted that the release process
and synthetic verification did not prove the real previous-release update
path. New beta invitations were paused.

The user's frustration was specifically about release reality, not merely test
coverage: beta clients had been told to update, but the official prior wheel's
own documented update path could not complete. The correction was accepted as
a release-process failure. "Implemented", "tested", "packaged", "released",
"installed", and "verified on a prior client" must remain separate claims.

## Product philosophy correction carried into this work

During the same discussion, the user corrected an architectural
misinterpretation. WOM is not trying to reproduce an enterprise ontology that
requires specialized entity mapping. Its distinctive direction is to avoid
making entity mapping the primary authority and instead preserve the durable
artifacts through which a person's understanding of a subject changes over
time. Contradictions, revised meanings, and chronology are evidence, not dirt
to be normalized away.

The absence of a dedicated dashboard is also intentional in the current line.
The primary UX is a frontier model operating through a desktop coding host
while following WOM's archive rules, safe command routes, and approval gates.
Internal complexity is still a legitimate product risk, but lack of a separate
visual UI is not itself a missing feature for this checkpoint. The superseded
external harness concept is not part of the current product description.

## Root cause

The Git snapshot used by ordinary project preflight enumerated only untracked
entries that were not excluded by Git ignore rules. An ignored entry could
therefore exist while `unexpected_worktree_entry_count` remained zero.

More importantly, the dry-run returned `ready_for_approval` before invoking the
read-only full-tree materialization probe. The approved path invoked that probe
only after fetch and target verification. The two modes did not share one
materialization decision, so preview could give a false green result even when
the exact local target tag was already available.

Existing tests proved that approval preserved an ignored collision, kept the
source and pins unchanged, removed its lock, wrote no receipt, and did not echo
the private filename or bytes. They did not assert dry-run/approval parity.

## Severity and immediate response

This is not a data-loss or secret-disclosure P0: the approved writer failed
closed before source or pin mutation. It is a P1 product and preview-contract
failure because the official dry-run omitted an approval-critical check and
provided no inspect or remediation route.

The public v0.3.314 GitHub Release was updated with a prominent known-issue
warning. Operators are told not to guess, delete, move, or repeatedly approve
ignored entries and not to continue to index or mint. v0.3.315 is the intended
superseding hotfix.

## Accepted implementation direction

- One bounded structured materialization planner must be shared by dry-run and
  approve whenever the exact target is local.
- An unfetched target must report that materialization inspection is deferred;
  it must not claim that the checkout plan has passed.
- Results must expose stable blocker codes, bounded counts, safe entry kinds,
  opaque entry references, and whether remediation is supported, without
  exposing ignored local names, absolute paths, private bytes, or private byte
  hashes.
- A single CLI-only conflict-control surface may inspect a verified target
  collision and, for a narrowly supported regular ignored untracked file,
  preview or approve identity-bound preservation outside the source mirror.
- Preservation must be no-overwrite, no-delete, separately approved, receipt
  backed, and followed by a fresh update dry-run rather than automatic retry.
- Reparse points, links, special files, directories, unreadable entries, drift,
  or exceeded bounds remain fail-closed and are not automatically remediated.
- Operation-control next actions must point to the conflict inspection route
  for this blocker without replaying private failure text.

## Completion boundary

The hotfix is not complete until focused adversarial tests, full regression,
independent security review, package synchronization, exact wheel verification,
public release verification, and the client sequence from update through fresh
index health and mint preview have each been separately evidenced. Real client
mutation remains outside this development thread unless the user explicitly
authorizes it.

## Implemented correction and review closure

- Dry-run and approval now share the exact target materialization planner.
  One private cross-map covers raw current/target/index/worktree names under
  NFKC, case-folding, HFS-ignored characters, Windows trailing/reserved/`.git`
  aliases, and conservative 8.3 rejection. Ignored aliases and empty ignored
  descendant directories block.
- Approved update rechecks exact HEAD, target/tree mapping, and tracked bytes
  before source mutation. A provable pre-HEAD failure uses bounded
  self-rollback; uncertain rollback retains the owned lock and evidence.
- The separate CLI collision surface accepts only the opaque entry ref plus the
  exact plan digest. Eligible preservation is a no-replace, same-volume Windows
  rename with handle-bound private intent/completion evidence. It never deletes
  or overwrites the payload, copies as fallback, changes a pin, or retries the
  updater.
- Terminal and exception projections distinguish fresh preview truth, final
  lock truth, and unknown write/relocation outcome. The private receipts prove
  unauthenticated internal consistency only, not signature-grade or same-user
  hostile-write protection.
- `operation-control` now routes allowlisted updater statuses separately and
  never turns a complete saved output into generic domain success.
- Focused feature/security review closed known P0/P1 findings before this
  release documentation and package pass. Full release evidence, prior-client
  installation, and human acceptance remain later, separate gates.

## 2026-08-12 final pre-write source recheck

An independent functional review found one remaining timing gap. The approved
updater checked its exact source snapshot, emitted the content-free
`checkout-release/start` progress event, built the bounded materialization
plan, and then started path writes. A tracked file changed during that interval
could be replaced by the target bytes even though the earlier checkpoint had
passed.

The materializer now receives the exact approved source snapshot and project
root. After planning and immediately before its first filesystem mutation, it
recomputes the full Git/source snapshot and requires exact equality. A mismatch
raises an internal fixed condition that the updater projects as
`project_version_update_source_changed_before_materialization`. The result is
blocked, the changed bytes remain exact, `HEAD` and pins remain unchanged, no
receipt is written, the owned lock is released, and the previous approval may
not be reused.

A deterministic regression changes a tracked runtime file from the progress
callback and verifies all of those properties without exposing the path or
bytes. The complete Letter 127 integration group then passed 51/51, and the
Letter 128 batch/recovery integration group passed 115/115 on the same tree.
