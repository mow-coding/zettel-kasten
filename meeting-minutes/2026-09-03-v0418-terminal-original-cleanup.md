# v0.4.18 Terminal Original Cleanup Work Record

Date: 2026-09-03

Status: implementation candidate; merge, tag, public release, and client-run
validation are recorded in the release section below as they occur.

## Context and user intent

The user handed implementation back to Claude for beta letter 153 after the
v0.4.17 release. The tester had installed the v0.4.17 bootstrap correctly,
watched identifier-free `--resume` compact two abort histories, and then hit
a new loop: dry-run reported `terminal_cleanup_required` and pointed at
`--resume`, `--resume` failed at the verify-release stage with only a generic
command failure, `operation-control recovery-plan` offered no next step, and
the next dry-run pointed at `--resume` again. The tester had to attach a
read-only wrapper and read the bootstrap source to learn that the real
exception was `exact_human_approval_state_unknown` wrapping
`project_version_update_preapproval_recovery_failed`.

The user's standing rules applied: fix the release, never touch the client's
workspace, release each batch as soon as its prep completes, and keep
interruptions to a minimum. The private report was read only; no client
archive, project, pin, lock, transaction artifact, credential, or provider was
touched. Public code, tests, and records use synthetic fixtures and do not copy
private paths, identifiers, digests, or report contents.

## Investigation

Seven parallel read-only tracers covered the resume router, the claim
lifecycle, the transaction module, the dry-run classifier, the CLI exception
boundary, the test fixtures, and the repository records; twenty-one
adversarial votes then attacked seven claims drawn from the report.

Confirmed: the client's remaining directory is a completed transaction whose
predecessor cleanup plan (`cleanup-plan.json`, schema v0.4.3) is durable inside
the original directory with no tombstone, no proof, and no terminal handoff.
The v0.4.15 `exact_cleanup` wrote the plan before the tombstone rename, and a
caught rename failure leaves exactly that shape; a v0.4.17 tombstone restore
followed by a downstream failure leaves byte-identical contents. The lockless
locator accepts a `completed` tail, the namespace classifier labels it
`resume_required_exact` without consulting terminality or the plan, dry-run
therefore routes to `--resume`, and `--resume` passes every gate into approval
claim rediscovery.

Corrected: the report's two hypotheses for zero claim candidates were both
wrong. Claims are never consumed (status is a closed set and the finalizer
touches only the project journal), and the approval context is rebuilt from
the sealed private plan, not from a fresh preview. The operative cause is the
succeeded-claim guard requiring `complete_exact` live components against the
v0.4.14 intent; the client's pin is now v0.4.15, so the pin classifies as
unknown, the guard silently drops the still-valid succeeded claim, and the
only fallback (claimless preapproval cancellation) structurally cannot accept
a completed forward journal. That fixed service reason was then masked by the
workflow's `from None` wrapper and again by the CLI allowlist.

Also confirmed: the predecessor cleanup authority equals the journal's
`approval_bound.approval_reference_sha256`, which is repeated through
`completed`, and the current `exact_cleanup` primitive already tolerates the
shape mechanically; only its callers derived authority from a live claim or a
terminal handoff. The report's statement that `preimages/` and
`private-bindings/` were empty is inconsistent with the observed dry-run
(`open()` would refuse) and is treated as a listing error, not a code fact.

## Design and independent review

The first design routed every handoff-less completed original into a new
cleanup route authenticated by the archive claim. Two independent adversarial
reviewers then found five blocking flaws, each of which changed the
implementation before any test was declared final:

1. Turning every non-matching completed original into unresolved residue
   would have regressed completed claimless cancellations and the v0.4.17
   stable-active-handoff state. The classification is now three-valued: exact,
   not applicable, or refused; only positive contradicting evidence becomes
   cleanup-outcome-unknown.
2. The route's own most likely failure (rename refused after the identity-bound
   sidecar was written) would have recreated the dead end. The inspection now
   accepts a current-schema plan bound to the live directory identity with
   journal authority, and a restored tombstone is re-classified after
   restoration.
3. Accepting a plan-less completed original granted deletion authority with no
   member binding. Plan-less originals keep the generic route.
4. Failure results asserted that the key and claim store were not accessed
   after they had been. Both flags now report truthfully, and the completed
   result carries them as well.
5. Waiving current-postimage validation for a superseded transaction and
   accepting the claim reference as cleanup authority for originals are design
   shifts that needed an explicit decision. The decision log records both, and
   the pin comparison keeps the v0.4.16 replay contract in force when the
   post-image is intact, with the new cleanup as its fallback after the fixed
   candidate-missing gate.

Non-blocking review items adopted: an unreadable or foreign sibling claim no
longer blocks recovery (the reference digest covers the approval id, so a
sibling can neither hide nor forge a match), the fixed inner reason also
accepts transaction-module codes, and the completed result separates the proof
written by this run from the namespace proof count. Deferred: caching the
repeated full-tree inspection during one resume, and a keyed re-check of the
journal approval MAC against the claim.

## Implementation summary

- `project_update_transaction.py`: `TerminalOriginalInspection`,
  `classify_terminal_original_for_resume_read_only`, and the exact-only
  wrapper.
- `exact_human_approval.py`: `_authenticated_claim_document_core` shared by
  the routing core and the new `_authenticated_claim_reference_core`, which
  returns the MAC-verified public reference and status without a context.
- `archive_services.py`: `terminal_original_exact` in the namespace classifier
  and every consuming set; the fresh-preflight result with the new basis; the
  resume arm with the pin comparison, the fallback after the candidate-missing
  gate, and post-restore re-classification; the guarded route with claim
  re-authentication, truthful key and claim-store flags, and fixed outcome
  bases; the POSIX platform-unsupported result.
- `exact_human_approval_workflow.py` and `archive_cli.py`: fixed
  `cause_code`/`cause_stage` on the wrapped workflow error, allowlisted into
  the redacted `--output` artifact and one fixed stderr line.

The route holds the project terminal guard from the final read-only
observation through cleanup, re-authenticates the journal approval reference
against exactly one succeeded claim, reuses the exact cleanup primitive
(identity-bound sidecar, no-replace tombstone, plan-bound deletion, one
canonical proof), and touches no project-domain file. The result attributes no
past success and requires a fresh preview and one new approval for any new
update.
- Documentation batch: release note, CHANGELOG, UPGRADE (EN/KO), README (EN/KO
  and kit), project-version-update, exact-human-approval contract, capability
  matrix, operator capabilities, runtime entrypoints, version truth source,
  install guides (EN/KO), documentation map (EN/KO), philosophy evidence
  (EN/KO), runtime skill and its packaged copy, supply lock v0.4.18 and policy,
  version metadata, and historical release-document tests.

## Verification

Focused cross-platform tests cover the three-valued classification and every
drift refusal, dry-run/approval parity on the exact shape and on tampered
authority, the generic route for a plan-less original and for a pre-unlock
handoff, the intact-pin fallback after the fixed candidate-missing gate, the
POSIX zero-write refusal, and the fixed inner cause code at the workflow and
CLI layers. Windows tests cover the fail-closed authority cases (absent store,
mismatched reference, started claim), the complete cleanup with a synthetic
MAC-verified claim, re-entrancy after a rename failure, and a restored
tombstone finished without claim rediscovery. The CLI end-to-end test performs
a real approval, recreates the predecessor shape, moves the pin, and proves
that `--resume` returns `terminal_transaction_cleanup_completed` without the
domain writer, durable-state reopen, or native approval. The existing v0.4.15
tombstone replay tests, including the real-predecessor hard-exit worker,
remain unchanged because the pin comparison keeps their route.

The complete project-update transaction module, the v0.4.16 terminal-create
recovery module, the exact-human workflow module, and the operation-control
module passed locally on Windows before the documentation batch. The complete
CLI project-version-update subset, release-document, package-resource,
privacy, runtime-skill, and readiness gates are recorded below.

## Human boundary

The person has the same two decisions as in v0.4.17: whether same-project
writers are paused for the complete transaction, and whether to update after
recovery and a fresh preview. WOM owns classification, authority
re-authentication, exact deletion, proof retention, and postconditions.

## Public release and independent installation evidence

The reviewed head was `94605566cbb336b70a917efb8c1b3868301c7b3e` on branch
`claude/v0.4.18-terminal-original-cleanup`. Its full pull-request CI run
[#33700612500](https://github.com/mow-coding/zettel-kasten/actions/runs/33700612500)
completed with every test shard (Ubuntu 3.12 and 3.10, two shards each;
Windows 3.12, four shards), the Doctor and link-index scale gates, the release
readiness gate, and the required aggregate job successful. PR
[#95](https://github.com/mow-coding/zettel-kasten/pull/95) was merged without
changing its reviewed head. Merge commit
`c0af18350cd154059b25523afd50ae558f29ba8f` has exactly the previous main
`40c5b4bbfc285eeaf23dc5931a3a1b851e6ba4cf` and the reviewed head as its two
parents. The exact-merge main run
[#33704450598](https://github.com/mow-coding/zettel-kasten/actions/runs/33704450598)
also passed.

The release wheel was rebuilt from that exact merge commit in a clean
worktree by the installed-wheel checker: 169 manifested resources verified,
runtime-skill lifecycle, onboarding preview/fixed-close, and the strict Doctor
fixture green, wheel SHA-256
`ab8d07f57c50b97ba35db56112629227838916e054bc584f3c8ba8b1552f8041`.

Annotated tag `v0.4.18` was created at the merge commit, verified locally and
through the remote peeled reference as `c0af1835…`, and pushed. Its push run
[#33704581159](https://github.com/mow-coding/zettel-kasten/actions/runs/33704581159)
passed. [WOM-kit v0.4.18](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.18)
was first uploaded as a draft binding the committed release-note body and one
asset named `wom_kit-0.4.18-py3-none-any.whl`. GitHub reported the asset digest
`sha256:ab8d07f5…8041`, identical to the locally verified wheel, and only after
that comparison was the release published and marked latest
(2026-09-03T01:40:39Z). The `releases/latest` API now resolves to `v0.4.18`.

The public release API and the wheel download were then fetched without an
authorization or cookie header; both returned HTTP 200 and the downloaded
bytes reproduced the same SHA-256. A fresh external CPython 3.12 virtual
environment installed only that anonymous wheel: `pip check` reported no
broken requirements, a new process returned `archive 0.4.18`, the installed
manifest reported version `0.4.18` with 169 resources, and the installed
`direct_url.json` bound the same wheel SHA-256.

GitHub reported zero open secret-scanning alerts after publication. The merged
feature branch was removed remotely and locally, and the canonical checkout
was fast-forwarded to the merge commit with a clean worktree. No client
runtime, archive, credential, provider, pin, or client data was read or
changed by this release execution.

## Release and client boundary

Publishing or installing the wheel changes no client archive or project. The
tester must separately run identifier-free `--resume` on the Windows machine
that owns the project, run a fresh preview, make one normal update decision,
and exercise the ordinary workflow. Until that client-side execution and its
durable evidence succeed, beta letter 153 is release-addressed but not
client-validated or resolved.
