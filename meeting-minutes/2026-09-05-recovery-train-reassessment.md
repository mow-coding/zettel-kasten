# Recovery train reassessment and implementation restart

Date: 2026-09-05
Status: accepted; v0.4.19 implementation resumed, not released

## Conversation and correction

The user requested a fresh evidence-based assessment before continuing the
existing six-release recovery and operations plan. The user explicitly said
that beta testers can wait: dependency correctness and avoiding repeated work
matter more than moving an apparently urgent feature ahead of its foundations.
The resulting plan was explicitly approved for implementation.

The audit covered all 162 Markdown feedback documents and three JSON evidence
documents in the supplied feedback collection. Original private documents,
labels, credentials, filesystem paths, provider identifiers, and raw client
content are not reproduced here. Later corrections, withdrawn claims, actual
client successes, public releases, and unperformed client actions were treated
as different kinds of evidence.

The conclusion was neither that nothing worked nor that shipping commands
resolved the workload. Several single-item creation, publication, capture,
linking, and deduplication tasks have real successful client reports. Other
previously usable operations were closed during the exact-approval migration.
Tests of individual commands repeatedly failed to prove the complete user
journey through preparation, approval, execution, restart, and verification.

The previous near-ready assessment of v0.4.19 was corrected. A synthetic replay
still rejected both runtime and source directories when only directory
`st_size` changed from zero to an allocated size. The installed bytes stayed
identical. Also, the same-version no-op built a complete candidate before
recognizing the existing runtime. Doctor's count-scale object files were only
30 bytes each, so that benchmark cannot prove large-byte client performance.

## Starting checkpoint

- Public main and the observed remote main were `95e3a8b3`; latest release was
  v0.4.18. There was no open PR or open secret-scanning alert.
- The preserved integration branch was 15 commits ahead of main at
  `17f6c77c`, with 52 existing modified or untracked paths.
- v0.4.19 had not been released. Later releases in this train had not begun
  integrated implementation; reusable older domain components already exist.
- No client archive, runtime, credential, provider, feedback ledger, or shared
  PATH installation was modified during assessment or this restart.

An absence of open secret alerts is not proof that a repository contains no
private material. Every public candidate still needs the privacy gates.

## Revised sequence and omitted outcomes restored

1. v0.4.19: runtime/source directory identity, a verified pre-download no-op,
   bounded predecessor recovery, four-state observations, capability truth,
   current-index behavior, meaningful Doctor performance, and hidden background
   process launches.
2. v0.4.20: work-session identity and compatible legacy resume, common local
   target preview, complete pagination, and **working session-scoped Git
   commit/push with remote verification before any subsequent client repair**.
3. v0.4.21: discard/restore, semantic revision/restore, publish/retire/edge
   batches, source-property recovery, title and receipt audit, locator/occurrence
   repair, already-captured object outcomes, and each operation's actual revert.
4. v0.4.22: reuse existing secure credential components and complete the Notion
   recovery chain, including the distinct historical locator recovery cohort.
5. v0.4.23: reuse existing object-store transport, verify complete remote bytes,
   safely offload approved local bytes, and automatically rehydrate on demand.
6. v0.4.24: relation acceptance, artifacts and external registered work roots,
   historical approval/source evidence review, exact legacy retirement, final
   session backup, and evidence-backed feedback accounting.

Common preview moves to v0.4.20 so later writers do not each invent it. Old
approved manifests and checkpoints remain immutable: session introduction may
record responsibility but cannot silently change the operation already
approved. A real source/pin/field conflict is not repaired by inventing evidence.

Withdrawn search-absence reports and already-confirmed capture, paired intake,
context, and duplicate-row fixes are preservation/regression requirements, not
new implementations. IMAP, Tiro, and unrelated provider extensions remain
explicit separate backlog items. They are not counted as resolved by this train.

## Implementation split and feedback loop

- Runtime work owns the shared runtime module and dedicated new synthetic
  identity/no-op tests.
- Doctor work owns the scale fixture and associated performance tests.
- Integration owns service routing, cross-domain installed-wheel tests,
  documentation, independent review, supported-platform CI, publication, and
  cleanup. A separate read-only review checks capability and observation gaps.
- Existing dirty work is preserved. No branch, worktree, or temporary artifact
  is removed merely because it is unfinished.

Each completed implementation/test step is appended here or linked from the
acceptance register. Public completion and real client verification remain
separate. The client-side AI performs project updates, native approvals,
recovery, independent verification, and backup using supported WOM paths;
development does not perform those private writes.

## Durable specifications

- [Acceptance register](../wom-kit/docs/recovery-operations-acceptance.md)
- [Decision amendment](../wom-kit/docs/archive-infra-decision-log-2026-09-05-recovery-train-amendment.md)
- [Earlier chronological implementation record](2026-09-04-v0419-v0424-recovery-operations.md)

## Implementation and independent-review observations

- Runtime directory snapshots now ignore allocation size for directories only;
  membership, identity, file bytes, and reparse checks remain. Independent
  synthetic source-mirror tests also preserve identical bytes under a
  directory-size-only change and reject actual file changes.
- A retained-runtime verifier checks exact retained wheel/dependency bytes and
  trusted startup files before executing fresh-process probes. The updater
  uses this before candidate download/build and repeats the existing fourteen
  revalidation dimensions. Probe timeout or launch uncertainty is unavailable,
  not permission to repair. Independent review found and corrected that
  distinction before release.
- Public create-draft preflight now separates valid input from current-index
  write readiness. Missing/stale indexes have a supported action; unreadable
  state does not authorize index rebuilding. AI provenance dispatch uses the
  same predicate as the service, including mixed declared provenance.
- Public command-tag evidence distinguishes nine formerly exposed approval
  paths from unaudited history. Exposure is not proof of successful use and
  does not recommend an older-version approval workaround.
- The real synthetic CLI/broker/runtime journey exposed a further integration
  error: a successful no-op left terminal pre-intent control history that
  blocked the next ordinary preview. The correction uses only that invocation's
  exact abort receipt to compact its own history into the established inert
  proof. Partial cleanup must not return a completed no-op. End-to-end replay
  and fault validation are still pending at this checkpoint.
- The historical count-scale Doctor run passed operational 76.730083 seconds
  and deep 85.847179 seconds. Its 22,441 objects totaled only 673,230 bytes and
  its mint evidence reused two source/snapshot pairs. Those numbers are not
  large-object or client-performance claims.
- A separate varied-size/independent-source fixture exposed a materially
  slower run. No success has been assigned to that expanded gate. Diagnosis
  will reuse the exact synthetic fixture instead of regenerating it repeatedly.
- Reusing that fixture isolated the repeated-work defect: one ordinary inbox
  draft invoked the retirement write planner, which spent about 15.5 seconds
  revalidating the whole index. Doctor called that path for every draft. The
  read-only diagnostic is being moved onto Doctor's existing bound input
  observations; actual retirement plan/write guards remain independent.
- Four real Windows own-reservation closeout tests passed, including a
  competing writer. Review caught a generic result that reported no lock
  despite that successor lock; a fresh tri-state presence observation corrected
  the report without touching the successor's bytes.
- The actual installed-wheel journey is now part of the checker and runs from
  isolated installed modules, not imports from the checkout. Its first full
  local run is diagnostic while source corrections are still being finalized;
  only final reviewed candidate evidence can satisfy release acceptance.
- The required CI now includes both Doctor profiles and the existing real
  installed-wheel workflow checker. Fixture preparation/job timeout and the
  unchanged 180-second operational measurement are explicitly separate.

All listed changes remain development-candidate work. Full candidate CI,
publication, anonymous asset verification, cleanup, and client execution are
not complete at this checkpoint.

## Installed-flow and scale-fixture review checkpoint

- The real candidate-wheel updater/no-op/follow-on-preview/launcher journey
  returned validated success before a later legacy runtime-skill assertion
  failed. The full checker therefore still failed; the partial journey result
  is diagnostic, not final candidate or public-release proof.
- Broader release-document regression testing found five stale expectations:
  four current citation dates and one conditional-approval count. The current
  date expectations now agree with this candidate and the count includes the
  actual create-draft provenance predicate. Historical release dates and
  successful-use claims were not rewritten.
- The Doctor optimization initially missed genuine minted twins when their
  retired-receipt parent directory did not yet exist. Existing public
  mint/validate/retire regression testing found it; a narrow parent-absence
  observation corrected it without weakening the safe resolver. Four durable
  tests now cover that case plus completed-inventory source/receipt drift.
- Review of the expanded synthetic fixture found mismatched source and target
  IDs, which exercised unmatched drafts rather than genuine minted twins. Its
  earlier performance failure remains useful diagnosis, not genuine-twin
  coverage. The corrected fixture binds matching source/target IDs and is being
  generated once for the final mixed-profile measurement.
- In-process Doctor timing begins after imports. Fresh public-process startup
  is a separate acceptance measurement; a quick handler status must not hide
  interpreter/module startup delay. Installed-process evidence is being checked
  before claiming the two-second first-status target.
- A bounded compile-only reproduction measured about 6.24 seconds for the CLI
  module and 12.03 seconds for the service module. Project runtimes intentionally
  disable generated bytecode, so an early print inside the same large module or
  a Python thread cannot establish the complete startup/heartbeat contract.
  The chosen correction is a small public CLI entrypoint with a content-free,
  lifetime-bound preparation heartbeat and handoff to the existing reporter.
  Earlier target releases retain their original launcher module. MCP and old
  direct module invocation remain compatible; improved startup is measured on
  the new supported console and project-launcher paths.
- The corrected full mixed fixture completed deep verification in 132.827
  seconds with one complete hash per object. Its operational run stayed within
  180 seconds but returned a failing diagnostic, so the combined gate remains
  failed. The same fixture is retained to expose content-free error counts and
  isolate that discrepancy instead of rebuilding it or weakening the gate.
