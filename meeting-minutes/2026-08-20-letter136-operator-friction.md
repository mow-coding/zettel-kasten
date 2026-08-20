# Letters 136–137 — Operator Friction and Approval-Integrity Remediation

Date: 2026-08-20

Status: v0.4.0 implementation in progress

## Trigger

The user supplied the protected operator feedback now referred to publicly as
`Letter 136` and asked that
work begin immediately. The feedback body was read from the protected personal
archive as read-only evidence. No archive, profile, zettel, objet, receipt,
credential, provider, or feedback record was changed.

Private record identifiers, hashes, byte counts, schema details, and intake
state were deliberately omitted from this public project record. They remain
only in the protected source system.

## User intent

The requested outcome is an implementation response, not merely a summary of
the feedback. The work starts from current public main in an isolated
development worktree. The protected personal archive remains outside the write
scope.

## Initial problem map

The thirteen reported frictions form four connected groups:

1. managed scratch scope, required-path discovery, archive-root resolution,
   remediation hints, and command-local usage output;
2. deterministic dry-run replay, approval digests and timestamps, proposal
   document shape, and stable approval-field locations;
3. source-fidelity evidence for external conversations or sessions and facet
   discovery or unknown-key warnings;
4. target-based link-receipt lookup plus safe feedback-reference correction or
   withdrawal.

The implementation must preserve the parts that worked well: batch intake,
separate plan/write approval boundaries, and receipt-backed link rollback.

## Working boundary

- Development worktree:
  `codex/letter136-operator-friction`, based on main commit
  `45a7d15449a10746f3d5b12387bcda64bcf9b512`.
- No real archive command from the reproduction list is run against personal
  data.
- Reproduction uses source inspection and isolated temporary fixtures only.
- Product, tests, public docs, schemas, versioning, and release records will be
  updated together after the exact implementation scope is frozen.

## Constraints carried into implementation

- Target-based receipt lookup, reviewed session evidence, and facet discovery
  are compatible new public surfaces, so the release must follow the minor
  version path rather than being described as a patch-only correction.
- Mutable-looking operations must remain append-only or receipt-backed; no
  existing immutable history may be silently rewritten.
- Approval guidance may expose field names, locations, command templates, and
  content-free codes, but not private values, local absolute paths, bodies, or
  credential material.

## Scope decision

The code audit confirmed that the report combines diagnostics fixes with new
compatible public capabilities. The response is therefore scoped as v0.4.0,
not as another v0.3 patch. This follows the repository's semantic-versioning
rule that compatible new commands, tools, or optional protocol fields advance
the minor version.

The implementation is split into three reviewable clusters:

1. make managed scratch scope explicit, detect but never delete an unmanaged
   project scratch root, validate the archive root before private request-path
   checks, add fixed index-rebuild remediation, and keep argument errors local
   to the selected subcommand;
2. make deterministic approval replay explicit, add one common additive
   approval-handoff envelope, describe complete revision proposals accurately,
   expose a read-only facet vocabulary with warnings rather than a breaking
   allowlist, and add a reviewed private session-evidence authority alongside
   the existing manifested-objet authority;
3. add bounded receipt-authenticated link lookup for the existing
   revert-and-relink workflow, keep immutable feedback references immutable,
   verify body-first records when possible, warn on legacy generic references,
   and expose the existing archived transition as the official withdrawal
   route.

Direct mutation of an old link receipt or feedback reference remains out of
scope. Existing receipts and history stay immutable; corrections use new
reviewed operations or append-only lifecycle transitions.

## Implementation start

Three independent read-only audits mapped the thirteen items to product and
test surfaces. Implementation then started in the isolated worktree with
non-overlapping ownership for the three clusters above. No command from the
feedback reproduction list has been run against personal data.

## Follow-up evidence: feedback 137

While implementation was in progress, the user supplied the protected reviewed
request now referred to publicly as `Letter 137`. It was read as protected, read-only
evidence and was not composed, recorded, delivered, or otherwise mutated.

Its private identifier, hash, exact schema, byte count, and intake metadata are
not reproduced in this public record.

The follow-up shows that the original usability failures can produce integrity
failures, not merely extra work. In particular:

1. long-lived human-facing reports can accumulate outside the managed archive
   scratch boundary while the in-archive lifecycle inventory also remains
   unclosed;
2. a caller can currently assert a `person:*` reviewer and CLI affirmations
   without presenting a one-use receipt bound to the exact reviewed body,
   frontmatter, warnings, checklist, and operation;
3. an AI-authored body can be captured as an objet and then used as its own
   mechanically verified source, creating circular rather than external
   fidelity evidence;
4. existing canonical, edge, and retired-draft receipts lack a product-level
   audit and append-only repair route for missing human approval or circular
   source authority;
5. artifact duplicate blockers and conflicting local agent instructions lack
   bounded classification and next-step guidance.

## Expanded v0.4.0 safety scope

The implementation plan now also includes:

- an approval-gated human-artifact registry and lifecycle writer, plus a
  content-free closeout gate over managed and explicitly registered external
  roots;
- one-use exact-review handoff receipts required by high-impact publication,
  edge, retirement, warning-override, and affirmation paths;
- circular self-source detection and a reviewed multi-source bundle/summary
  authority that never claims machine verification of semantic fidelity;
- read-only approval-integrity audit plus append-only quarantine, evidence
  supplementation, withdrawal, and repair planning without deleting or
  rewriting historical receipts;
- duplicate-object classification/reconciliation guidance and startup-time
  local instruction conflict detection with an explicit policy precedence.

Compatibility must be explicit. Existing v0.3 receipts remain readable for
audit and migration, but new high-impact writes use the stronger v0.4 approval
contract. No caller-supplied actor string alone counts as proof that a human
reviewed exact publication bytes.

## Exact interactive intent implementation

The approval-integrity work began with two non-overlapping product boundaries:

- `wom_kit.exact_human_approval_windows` uses the standard Windows
  `TaskDialogIndirect` surface. It displays only the operation label, archive,
  plan and target SHA-256 bindings, and fixed review/warning codes. A live
  decision requires both the dedicated approval button and the verification
  checkbox. The synthetic UI intent can acknowledge the dialog but can never
  return live approval.
- `wom_kit.exact_human_approval` turns a live decision into an authenticated,
  archive-bound, create-once claim below ignored-local `profiles/local` before
  the first write. The claim is one-use, persists `started` across crashes,
  reaches one terminal state, and exposes only random identifiers, digests,
  fixed states, and booleans. The supplied reviewer label is hashed and is
  explicitly recorded as an unauthenticated identity claim.

This follows the current Microsoft Task Dialog contract for an explicit
verification checkbox and result, and the NIST authentication-intent principle
that a person must explicitly respond to each transaction. The project does
not overclaim that a local click proves a legal identity or defeats malware;
the click establishes local interactive intent for one exact digest-bound
attempt. The existing archive-specific Windows key authenticates the durable
claim when the boundary is connected to live commands.

The initial pure/fake-native regression set covers live button-plus-checkbox,
synthetic non-authority, invalid context before native calls, content-free
errors, archive identity binding, create-once replay, HMAC tampering, terminal
states, key-buffer wipe, and finalization failure that deliberately leaves a
`started` reconciliation record. No actual popup, archive key, or archive write
was used by these tests.

## Completion correction and release boundary

The user explicitly corrected the working cadence after implementation paused
at an intermediate green CI state: the work is not complete at code review or
even merge. For this task, completion means the v0.4.0 candidate passes the
full regression and package gates, merges through a clean pull request, is
tagged and published as a public release, and is verified by an anonymous
download plus a fresh isolated install. This correction is now the controlling
end condition. The protected personal archive remains read-only throughout;
release verification must use synthetic fixtures and the published wheel.

## Exact-writer integration progress

The implementation then connected and hardened the actual mutation boundaries:

- AI draft creation and approved session evidence require the concrete
  authenticated claim, rederive the same approval context immediately before
  writing, and publish a separate authenticated approval-link receipt when a
  strict legacy receipt cannot safely grow a new field;
- mint, single zettel-edge write, draft retirement, promotion, and warning
  override bind their exact plan, target set, warning/checklist codes, and
  operation before the first mutation, while the workflow alone owns terminal
  claim finalization;
- compound and batch mutations are fail-closed until a complete compound
  target-set binding exists; a general task request or reviewer string is not
  treated as exact publication approval;
- human-artifact root registration and lifecycle transitions, duplicate-object
  reconciliation, and approval-integrity repair use the same concrete claim
  boundary rather than accepting caller-fabricated approval mappings;
- relationship revert routes were identified as an alternate legacy mutation
  path and are being fail-closed until an explicit exact removal binding is
  implemented.

During independent audit, a service-level duplicate-reconciliation bypass was
found even though the CLI used the correct workflow: the writer still accepted
a shape-valid caller mapping. Release work stopped at that boundary, and the
writer is being changed to require the concrete current claim and to assert it
immediately before mutation. A similar audit found that promotion service
hardening had made the old CLI unusable; the CLI was then connected to the
native approval workflow for both normal promotion and warning override. These
corrections preserve the fail-closed product boundary rather than adding a
test-only or compatibility bypass.

## Native task-dialog runtime check

The Windows approval surface was checked again against Microsoft's current
`TaskDialogIndirect` contract. The API requires Common Controls version 6 and
supports a verification checkbox plus an application-defined approval button,
which are the two inputs required by the implementation. The local Python 3.12
executable used for development was inspected without opening a window and its
embedded manifest contains the exact `Microsoft.Windows.Common-Controls`
version `6.0.0.0` dependency. The exported `TaskDialogIndirect` entry point is
also present. This is runtime-precondition evidence only; no synthetic or live
dialog was opened and no approval was issued during this check.

Official references:

- https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect
- https://learn.microsoft.com/en-us/windows/win32/sbscs/activation-contexts

## Explicit external-delivery registration

Letter 137 clarified that human-created files can arrive outside a project
scratch directory, including a delivery or download folder, and that closeout
must not silently ignore them. The implementation therefore added two explicit
registration kinds to the human-artifact registry:

- `external_project` scans only the approved root's `.wom-scratch` directory;
- `external_delivery` scans the approved root itself.

This is deliberately not an automatic home-directory or Downloads scan. The
operator must select the exact external root, review the deterministic plan,
and approve that one root through the exact-human workflow before it becomes a
scan or closeout authority. Public results expose only fixed scope labels,
digests, counts, lifecycle states, and booleans; private filenames, paths, and
content are not projected. Symlinks, reparse points, root-identity drift, and
unregistered roots fail closed. The registry records lifecycle evidence but
never deletes the artifact automatically.

The focused human-artifact module plus CLI/MCP regression set passed 14 tests,
including delivery-root registration, direct-root scanning, unresolved-file
closeout blocking, one native claim per write, MCP write rejection, and
content-free output. All tests used temporary synthetic fixtures. The
protected personal archive, actual delivery folders, and native approval UI
were not accessed.

## Literal all-affirm and alternate-writer audit

The implementation review returned to Letter 137's literal wording: the
requirement covers every public `--affirm*` write, not only the five initial
create, mint, edge, retire, and warning examples. Runtime parser inspection
found 22 commands with 35 affirmation options, plus four warning-override
options. `mint-zet` and `promote` have complete exact single-operation
bindings; the activity-group removal plan is read-only. Every other
affirmation writer now returns the same content-free
`compound_exact_human_approval_binding_required` result at both the CLI and
service boundary before it reads private input or changes a file.

The audit then followed alternate writers that could change the same canonical
or authority state without an affirmation flag. Migration and its six lower
public helpers, saved-view changes, markup normalization and recovery,
principal registration, object capture and capture enablement, external
imports, source binding, and ownership transfer were fixed-closed in the same
way. Durable and external-effect routes were audited next: object-storage
setup/upload/adoption/evidence, Notion ancestor and page recovery, source
intake, external locators, quarantine decisions, prehashed ledgers, and zet
delegation are now plan/audit-only until they receive their own complete exact
target-set binding.

The public credential and Notion workflow entry points close before credential
or provider access. Low-level injected engines remain available only inside
their modules so retry, tamper, rollback, and atomicity invariants can still be
tested; they are not exported through the package root, CLI, or MCP and are not
standalone approval authorities. This separation avoids replacing useful
algorithm tests with blocker-only tests while keeping every public execution
path fail-closed.

The first inventory fixed-closed 63 public commands whose `--approve` action
lacked a complete exact binding. Later exhaustive passes ultimately expanded
that top-level canonical inventory to 79 commands, plus the nested
`derive-text capture`, mixed `create-draft`, and no-approve `init` and
`parcel`/`pack` write surfaces. A central parser inventory rewrites each
affected help entry to say that the write is unavailable in v0.4.0 and that
only dry-run, plan, or audit mode may be used. Exact single-write commands
retain their operation-specific approval help. Dedicated help tests make a
missing or stale command entry fail during regression.

## Finalization truth and the second alternate-writer audit

An independent final audit found a release-blocking truth error in the common
exact-human workflow. The workflow had finalized every well-formed
`ok: false` writer result as a terminal failed claim. That is unsafe because
promotion, mint, draft retirement, and reviewed session-evidence writers can
commit an immutable operation receipt or canonical effect and then report a
later index, receipt, or final-verification failure. A terminal failed claim
would falsely detach the durable effect from the approval authority.

The workflow was changed so that only `ok: true` finalizes `succeeded`. Any
non-success after writer entry leaves the authenticated one-use claim
`started`, adds the fixed content-free
`approval_claim_reconciliation_required` result, prohibits automatic retry,
and preserves the writer's safe reconciliation evidence. Focused tests cover
the four concrete partial-effect shapes plus JSON and text CLI projection.

The same audit then inspected every remaining public approval route rather
than assuming the first fixed-close inventory was exhaustive. It found older
provider, credential, canonical-provenance, external-copy, bootstrap, and
source-registration writers that still trusted a flag, reviewer label, or
legacy receipt. These include Tiro recovery fetch and capture, the Notion
manifest locator label, derived-text capture, restore drill, repository setup,
KeePassXC write, IMAP manifest/header operations, source-map rescan, the
human-declared create-draft compatibility branch, and new-archive onboarding.
Their planning and audit modes remain useful, but their real write modes are
being fixed-closed until each receives its own exact operation binding.

Three legacy approval-record families were also found to overstate authority:
approval handoffs, credential-access approval receipts, and IMAP material
capture approval receipts. They remain readable as advisory, legacy-unbound
metadata, but v0.4 public results must never say that they authorize a future
operation. No real credential, provider, popup, personal archive, or external
delivery folder was accessed while making or testing these changes.

## Exhaustive boundary closure and deterministic mint replay

The exhaustive public-entrypoint review closed two final high-impact surfaces
that did not expose an approval flag at all. `archive init` could previously
create a complete archive from either CLI or MCP, and `parcel`/`pack` could
copy canonical zettel bytes into a portable workpack. Their non-dry-run paths
now return the same fixed blocker before target, template, archive, view, or
private zettel reads. MCP archive initialization defaults to dry-run. Historical
algorithm fixtures use checked-in templates directly; they do not call a
hidden production bypass.

The review also found an error-projection regression in four supported exact
single-operation CLI groups. Preflight failures in `zettel-edge`, `promote`,
`mint-zet`, and `retire-draft` could exit with empty JSON output or reflect a
private exception on stderr. They now return structured, content-free JSON in
JSON mode, preserve the blocked dry-run result without opening the approval
dialog, and keep the exact success workflow unchanged.

One real replay defect appeared during legacy regression testing. A mint plan
that contained an AI scratch cleanup generated a fresh timestamped cleanup
receipt locator on each dry run. Although the binding already excluded the
receipt field, the same locator was still present inside two `would_change`
projections, so an unchanged plan failed exact approval revalidation. The
binding now removes only that volatile cleanup-receipt write locator while
continuing to bind every cleanup candidate, candidate digest, policy fact,
canonical target, mint receipt, and snapshot target. A focused unit test proves
that changing only the timestamped locator preserves the plan digest while a
candidate digest change invalidates it; the original end-to-end AI-scratch mint
regression also passes.

The independent review of that determinism fix then found a separate deletion
race. After exact approval was revalidated, another process could replace an
approved scratch file at the same relative path before cleanup, and the old GC
path would delete the replacement without comparing it to the approved hash.
Mint now passes its approved cleanup projection internally to GC. GC compares
the fresh plan, preflights every candidate, and revalidates plain-file status,
size, open-handle hash, and file identity immediately before each unlink. A
drift preserves the replacement and returns the fixed
`canonical_written_scratch_cleanup_reconciliation_required` partial result.
Because canonical mint effects already exist, the workflow leaves the claim
`started` and requires reconciliation instead of falsely finalizing success or
retrying automatically. A synthetic replacement canary proves that the new
bytes survive.

An intermediate audit briefly reported no open implementation P0 or P1. The
pre-commit audit then deliberately reopened that conclusion after finding
additional public Python engine and approval-boundary bypasses. Those findings
are being closed and independently retested before the full suite and public
release workflow; the earlier checkpoint is not release evidence. No real
popup, provider, credential, protected archive, external delivery root, or
release action occurred during this checkpoint.

## Release-checker correction

The pre-release workflow was compared with the v0.3.320 public-release
precedent before building the candidate wheel. That audit found one stale
release-time assumption: `check_wheel_install.py` still invoked
`onboard --approve` and required a newly created archive, even though v0.4
intentionally fixed-closes that public writer. Leaving the checker unchanged
would either fail the real release or pressure the product boundary back open.

The checker now emits `wom-kit/wheel-install-check/v0.3`. In a fresh installed
environment it requires the onboarding dry-run to succeed, requires the real
write request to return the exact content-free compound blocker with zero
files written, and confirms the target was not created. It then runs strict
Doctor through the installed entrypoint against the checked-in fake archive.
The runtime-skill install and uninstall probes follow the same v0.4 boundary:
their dry-runs remain useful, while both approved writes must return the exact
content-free compound blocker and leave the target absent. The four installed
entrypoint probes remain live read-only checks. Unit coverage for the checker
contract passed 38/38. The actual clean candidate wheel check remains a later
release gate after all tests and resource synchronization are green.

## Late public-authority sealing audit

The pre-commit audit found that several command handlers were already fixed
closed while lower packaged Python engine names still exposed concrete claim,
credential, provider, storage, or recovery effects. It also found that the
generic exact-human workflow callback and injectable native/key seams could be
misused by a direct module caller. This was a real public-library boundary gap,
not a reason to reopen any command writer.

The v0.4 correction makes authority-bearing claim types and factories, native
facades, key providers, callback orchestrators, credential/recovery workers,
brokers, lifecycle committers, provider request engines, and private evidence
readers underscore-private and removes their old public module attributes and
exports. Public APIs retain safe plans, projections, validation data, and the
real operation-specific CLI workflow only. Missing or forged claims now fail
before private archive, source, credential, or target reads. Test suites reach
private cores explicitly to preserve fault-injection and atomicity invariants;
that test access is not a production authority path.

The same pass fixed standalone AI scratch cleanup and credential lifecycle
approval at both CLI and service boundaries, bringing the canonical top-level
fixed-close inventory to 75. It also corrected stale operator guidance that
recommended approving zettel-objet revert/relink even though both routes are
fixed closed in v0.4.0. Final P0/P1 status remains open until the independent
auditor reports no further public effect surface and all frozen test shards pass.

A later bounded audit added gitignore repair, runtime-skill install/uninstall,
and catalog-pass cleanup to the same boundary, bringing the exact canonical
top-level inventory to 79. It also rejected non-boolean dry-run and approval
values before every affected archive read so integer lookalikes cannot bypass
the fixed-close gate. These are release-boundary corrections, not new writers.

## Progress-control correction and Letter 138 intake

The operator challenged the release supervisor twice after the work appeared
to stop or loop. The correction was procedural, not cosmetic: do not present an
intermediate checkpoint as completion, do not rerun the full suite while source
security findings are still changing, and do not mix a newly reported recovery
incident into the security-release branch without first classifying whether the
current release can repeat the loss. The fixed order is now public-surface audit
and sealing, affected focused tests, one frozen-byte full validation, public
release operations, and then the separately bounded recovery release.

A new protected feedback letter reported that historical Notion migration had
silently omitted populated value properties. The supervisor read the protected
letter and migration code under a read-only boundary. No private identifiers,
property values, source digests, or protected paths were copied into this public
record.

The code trace confirmed multiple deterministic loss stages:

- the DB1 mirror used a property-type allowlist and never serialized ordinary
  email, phone, URL, number, or relation values;
- the DB2 mirror omitted several types immediately, temporarily retained some
  date, relation, rich-text, and file values, and then the draft builder wrote
  only a small subset and discarded the rest without an unmapped-value warning;
- the DB3 draft path reduced URL properties to a presence flag and preserved
  only selected date and relation shapes;
- later preparation and mint steps consumed the already reduced draft and did
  not re-read the source mirror, so they could not recover the omitted values.

The current v0.4 product does not contain the same generic
Notion-mirror-to-canonical writer. Its Notion recovery surfaces are page-body
or location recovery only; they are not a complete source mirror and do not
claim typed-property preservation or canonical backfill. Historical property-
loss detection and repair are explicitly outside v0.4.0.

Letter 138 is the urgent immediate follow-on data-integrity track. Its minimum
scope is a read-only typed-property loss audit, a generic lossless property
envelope, explicit mapping or human-approved drop decisions, populated-unmapped
fail-closed behavior, a mirror-versus-canonical aggregate audit, and an
exact-approval/CAS-bound idempotent backfill with recovery and rollback. The
public result must expose counts and fixed reason codes only; raw email, phone,
URL, relationship, or other private values remain private evidence.

## Frozen local validation and release handoff

After the public-authority inventory stopped changing, the final worktree was
frozen and validated without a real provider, credential, popup, protected
archive, or external delivery target. The deterministic four-way unittest
manifest covered 124 modules and 3,320 tests: 3,284 passed, 36 platform or
environment skips were reported, and there were no failures or errors. The
separate pytest-native CI set passed 210/210.

The standard wheel checker was then corrected to test the actual v0.4
runtime-skill and onboarding boundary instead of expecting retired approved
writes to succeed. The post-correction checker passed from a clean temporary
copy. It verified package version 0.4.0, all 156 manifested resources, 214 wheel
members, four CLI/MCP entrypoints, fixed-close runtime-skill and onboarding
effects, and strict Doctor on the checked-in fake archive. A second fresh
virtual environment passed installation, dependency checking, version/help,
strict Doctor, and all four release-readiness gates. The preserved candidate
wheel is `wom_kit-0.4.0-py3-none-any.whl`, 2,025,809 bytes, with SHA-256
`9b7432ce3ac9e9d62497ce3f5bf4e9e9a91a1088da73c611df2cfda6e92fcd76`.

This is pre-release evidence, not a claim that v0.4.0 is already public. The
remaining sequence is exact-path staging, implementation PR and required CI,
merge, annotated tag and GitHub Release with the verified wheel, anonymous
public-download installation, and a small release-verification closeout record.
Letter 138 recovery begins immediately after that release boundary closes.

## First public-CI correction

The implementation candidate was committed as
`c186b6f88e9f053c0a0da7beba9cda2171c82ec9` and opened as GitHub pull request
71. Its first Required CI run completed every job and exposed exactly three
test-contract problems; it did not expose a new product write bypass.

Two cross-platform symlink tests still expected legacy approved writers to
reach archive-path inspection. The v0.4 public writers now correctly return a
content-free compound-approval blocker before those reads. The tests were
split so the direct or dry-run path still proves `symlink_not_allowed`, while
the public apply path separately proves pre-read fixed closure, zero writes,
and no dormant-core dispatch.

One Windows MCP subprocess test closed stdout before the child had completed a
14-to-16-second cold start, then counted that startup time against a 15-second
BrokenPipe exit limit. The server did exit normally after startup, but the test
timed out first and failed to reap the child. The corrected test first receives
a ping response to prove server readiness, then closes stdout and measures only
the post-ready exit with a five-second bound. Its `finally` path always reaps
the child and closes all streams. A delayed-start reproduction, a deliberate
post-ready hang control, a 25-run ResourceWarning check, adjacent tests, and the
affected frozen local shards are required before the single CI-fix push.
