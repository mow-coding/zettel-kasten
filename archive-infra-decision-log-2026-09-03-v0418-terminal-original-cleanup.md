# Decision Log: v0.4.18 Terminal Original Cleanup

Date: 2026-09-03

Status: accepted implementation direction; public release evidence recorded in
the meeting minutes

## Context

A private read-only client report (beta letter 153) showed that v0.4.17 still
had one dead end. The client's remaining transaction directory was a completed
v0.4.14 update whose predecessor cleanup plan was durable inside the original
directory but whose tombstone rename never took effect, and the project had
since moved on to v0.4.15. Fresh dry-run classified it as exact terminal history
and pointed at identifier-free `--resume`. Resume treated it as a live approved
transaction, rediscovered the archive claim, and dropped that succeeded claim
because the live active pin no longer equalled the transaction post-image. With
zero candidates it fell into claimless preapproval cancellation, which refused
a completed forward journal, and the fixed service reason was masked twice into
a generic command failure. The next dry-run pointed at `--resume` again.

Independent tracing corrected two hypotheses in the report: claims are never
consumed, and the approval context is rebuilt from the sealed plan. The
operative cause was the succeeded-claim live guard requiring `complete_exact`
against a post-image the project had legitimately superseded.

## Decision

Use the existing `project-version-update` command and its identifier-free
`--resume` for the complete correction. Add no operator command and ask the
person for no identifier.

1. A still-present completed original is classified read-only as
   `terminal_original_exact` only when its journal is exact, forward, and
   terminal, no live lock, tombstone, or proof contradicts it, a retained
   cleanup plan (predecessor legacy schema, or the current identity-bound
   schema bound to that exact directory) names the journal approval reference
   as its cleanup authority, and the plan's members equal the current tree
   exactly. The classification is three-valued: exact, not applicable, or
   refused. Cancellation journals, rollback journals, plan-less completed
   originals, and current plans carrying a terminal-handoff authority keep
   their existing routes. Only positive contradicting evidence becomes
   `project_version_update_terminal_cleanup_outcome_unknown`.
2. Fresh dry-run, approval, and resume share that classification. Dry-run and
   approval return `terminal_cleanup_required` with the content-free basis
   `exact_terminal_transaction_cleanup_requires_resume`; resume finishes the
   directory instead of routing a completed journal into claimless
   preapproval cancellation.
3. The postimage rule of the v0.4.16 amendment is narrowed, not removed. When
   the live active pin still equals the transaction post-image, resume keeps
   the v0.4.16 replay contract (claim rediscovery, terminal handoff, bound
   result). When the pin has moved on, current-postimage validation is not
   required, because the transaction's domain effect is history and only its
   private control directory is reconciled. If the replay contract refuses
   through its fixed candidate-missing gate while the pin still matches, the
   same cleanup runs as a fallback in the same invocation.
4. Cleanup authority for that route is the archive's succeeded approval
   claim, re-authenticated by public-reference digest. The journal binds
   `sha256(canonical(public_reference))` at `approval_bound` and repeats it
   through `completed`; exactly one MAC-verified `succeeded` claim in the
   bound claim store must reproduce it. The retained plan remains historical
   evidence, never delete authority. No approval context is rebuilt, no live
   component is classified, and no key or claim is created. This accepts the
   claim reference as cleanup authority for originals as well as for restored
   tombstones.
5. The route holds the project terminal guard from the final read-only
   observation through cleanup, re-validates the observation under that
   guard, and reuses the exact cleanup primitive. A durable identity-bound
   sidecar beside the legacy plan and a restored tombstone are finished by the
   same route on the next resume. An unverified authority, an incomplete
   cleanup, or an observation change returns cleanup-outcome-unknown with a
   fixed basis and preserves evidence. Mutation remains Windows-only; POSIX
   returns `terminal_cleanup_platform_unsupported` with zero writes.
6. The completed result `terminal_transaction_cleanup_completed` attributes no
   past success, reports project-domain effects as none, records that the
   approval key and claim store were accessed, and requires a fresh preview
   and one new exact approval for any new update. A canonical proof produced
   this way grants no retry, cleanup, or fresh write authority.
7. The exact-human workflow may carry one fixed, code-shaped inner reason and
   its fixed wrapping stage on `exact_human_approval_state_unknown`. The CLI
   copies only allowlisted literals into the redacted failure artifact and one
   fixed stderr line; raw exception text, paths, values, and identifiers stay
   redacted, and the public workflow code and generic blocker are unchanged.
8. `marker.json` is an identity anchor whose `state: reserved` never changes;
   the verified checkpoint journal is the completion truth. This is documented
   rather than rewritten, because every open re-validates the marker bytes.

## Human responsibility

The person decides whether same-project writers are paused and whether to run
a fresh reviewed update after recovery. WOM verifies the journal, plan, tree,
claim, identities, cleanup selection, and postconditions. Private transaction
identifiers, approval identifiers, digests, and counts are never operator
inputs.

## Consequences

- The client's remaining transaction can be finished by the official
  `--resume` in one invocation, after which a fresh preview and one approval
  are possible again.
- Dry-run, approval, and resume cannot disagree about a completed original:
  either all three route to resume and resume can finish it, or all three
  report cleanup-outcome-unknown.
- The v0.4.16 replay contract, including result replay and terminal handoff
  publication for an intact post-image, is unchanged; the fallback only fires
  after its fixed candidate-missing gate.
- A masked service failure on the resume path now leaves a fixed inner reason
  in the diagnostics artifact, so a tester no longer has to read source to
  learn which gate refused.
- Every new public field and progress event is a fixed literal.

## Rejected alternatives

- **Route every completed original into the new cleanup.** It would drop the
  v0.4.16 replay contract for transactions whose post-image is intact and
  silently change the authority basis of v0.4.16 handoff shapes. The pin
  comparison keeps both contracts.
- **Accept a plan-less completed original.** Without a durable plan there is
  no member binding, so a foreign file in the directory could be deleted under
  journal authority. Plan-less originals keep the generic route.
- **Derive cleanup authority from the journal alone.** The approval MAC in the
  journal is keyed and cannot be re-verified without the claim; the
  MAC-verified claim document is the authenticated source.
- **Expose the wrapped exception text.** Internal service messages may carry
  private context; only allowlisted fixed literals cross the CLI boundary.
- **Rewrite `marker.json` on completion.** Every open re-validates the marker
  bytes against the sealed intent; changing them would invalidate old
  transactions for no truth gain.

## Verification and release gate

Synthetic fixtures only. Required regression evidence: three-valued
classification with drift refusals, dry-run/approval/resume parity, POSIX
zero-write refusal, fail-closed authority (absent store, mismatched reference,
started claim), the complete Windows cleanup with a synthetic MAC-verified
claim, re-entrancy after a rename failure and after a restored tombstone, the
intact-pin fallback, the existing v0.4.15 tombstone replay tests unchanged,
the CLI end-to-end superseded original, the inner cause-code artifact, full
project-update transaction and CLI modules, release-document, package-resource,
privacy, and readiness gates, and exact merge, tag, and release evidence.

Longer chronology and implementation notes:
[meeting-minutes/2026-09-03-v0418-terminal-original-cleanup.md](meeting-minutes/2026-09-03-v0418-terminal-original-cleanup.md).
