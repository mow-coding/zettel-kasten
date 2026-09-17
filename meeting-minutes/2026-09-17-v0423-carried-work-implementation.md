# v0.4.23 carried-work implementation record

Date: 2026-09-17 (Korea Standard Time)
Status: development in progress; not integrated, released, or client-verified

## Scope and sequence

v0.4.22 (the update-failure hotfix for beta letters 161 and 162) is the
release candidate on [PR #104](https://github.com/mow-coding/zettel-kasten/pull/104).
The user's direction for what follows: "그거까지 쭉 진행해. 그 다음에 클라이언트한테
답장할래" — continue straight through the work carried from v0.4.21, and only
then prepare one combined reply to the client. This worktree
(`zettel-kasten-v0423-work`, branch `claude/v0423-carried-work`) starts from
the v0.4.22 candidate head `c3bfb0be` and is rebased onto main after the
squash merge. Carried rows: letter 160 ② (binary evidence originals as the
fidelity source), letter 160 ④ (create-draft --approve under a PowerShell
scriptblock wrapper, unreproduced), LR-06 session integration of the 30
pending writer paths, LR-02 through LR-05 and LR-07. Held for the user's
decision: the session-scope pre-approval of letter 161 (request 6), because it
changes the one-dialog approval contract.

Executing model: Claude Fable 5.1, solo (no agent fan-out for any unit or
release step), under the user's standing approval for the train. Boundaries
unchanged: synthetic archives, temporary repositories and local bare remotes
only; the client workspace and its letters are read only; explicit staging
only; every decision recorded here and in the acceptance register.

Unit order (client impact first): U1 letter 160 ② (a concrete daily blocker
with a bounded fix), U2 letter 160 ④ (reproduction attempt on the exact
PowerShell 5.1 shape), then LR-06 by writer family, then the LR-02..05/07
revalidations.

## Unit U1: binary originals as the fidelity source (letter 160 ②)

Letter 160 ② reproduced: `create-draft --fidelity-source-object-id` with a
.xlsx or .pdf objet returned `source_fidelity_source_not_utf8` in every mode,
because the fidelity contract only knew the `utf8_newlines_lf` comparison
basis. The client asked for a mode that binds fidelity by byte-hash identity.

Design decisions:

- A second comparison basis, `bytes`, for the two modes that never claim a
  mechanical text comparison: `faithful_summary` and `sanitized_derivative`.
  No new flag: the mode already declares that the draft is a reviewed
  candidate, not a region copy, and the reviewed plan digest binds the basis.
  `verbatim` still requires a UTF-8 text objet (only a text region can be
  compared mechanically) and keeps returning `source_fidelity_source_not_utf8`
  with a next-safe-action that names the two modes that accept a binary
  original.
- On the `bytes` basis the source evidence records the raw digest as the
  normalized digest, equal sizes, `newline_transformation_applied: false`,
  and the unchanged absent-source-text and absent-locator facts. The receipt's
  fidelity block and evidence id carry the source's basis; text sources keep
  the `utf8_newlines_lf` basis byte for byte (same evidence-id input), so no
  existing receipt or replay changes.
- Every validator that compared the basis to the constant now accepts both
  bases with consistency: `bytes` only with a binary-source mode, the
  fidelity-level and source-level bases equal, and on `bytes` no newline
  transformation with normalized equal to raw. This is in the plan builder,
  the private receipt shape validator, the mint-time verifier (basis check and
  evidence-id recomputation) and the approval-integrity receipt validator.
  The reviewed-session-evidence authority stays text-only.
- Both draft receipt schemas (v0.1 file and v0.2 file) relax the
  `comparison_basis` const to the two-value enum for the fidelity block,
  the common source block and the manifested-object source; the
  reviewed-session-evidence source keeps the const. Existing receipts stay
  valid; no schema id changes. The packaged copies are resynchronized.
- `source_fidelity_policy()` gains `comparison_bases` and
  `binary_source_modes` beside the unchanged `comparison_basis` default, so
  the AI runtime and MCP surfaces can state the rule without parsing help.
- A binary source that is empty is refused with
  `source_fidelity_binary_source_empty` instead of the text-only
  non-whitespace code.

Evidence: `tests/test_v0423_binary_fidelity_source.py` (6 tests: verbatim
still refuses; a summary draft over xlsx-like bytes previews, approves,
validates against the schema, re-verifies at mint time on the stored basis and
replays idempotently; sanitized_derivative accepts; text sources keep the
UTF-8 basis; the stored validators refuse mode/newline/digest/basis
inconsistencies and the schema refuses an unknown basis; the policy
projection lists both bases). Regression cohort: the v0.3.313 fidelity,
CLI/MCP and docs tests, letter 136 facets, letter 137 approval integrity,
letter 159 draft promotion, private objet metadata index and predecessor
surfaces: 112 tests pass. Doc: a new section in
`docs/source-fidelity-and-private-verbatim.md`; the create-draft option help
says which modes accept a binary original.

## Unit U2: create-draft --approve under a PowerShell scriptblock wrapper (letter 160 ④)

Reproduction attempt on this machine (Windows PowerShell 5.1, the same shape
as the letter: `function Approve([scriptblock]$cmd){ & $cmd > $out 2>&1 }`),
against a throwaway copy of the fake-life example archive with the hotfix
wheel: results are recorded below as they complete.

- Human-authored replay (`--created-by person:...` with `--approve`): both
  shapes return the same fixed-closed answer
  (`compound_exact_human_approval_binding_required`); the human route does
  not use `--approve`.
- AI-authored replay (`ai_assisted`, one facet, `faithful_summary` over a
  manifested text objet): both shapes returned the same preflight answer
  (`archive_index_rebuild_required` on the stale example index); the wrapper
  changed nothing except that PowerShell 5.1 writes the redirected file as
  UTF-16. After rebuilding the index both shapes passed the preflight and
  reached the native approval dialog (the direct run was stopped after the
  15-second cap, the wrapped run after 6 seconds; a preflight refusal
  returns within about one second). The wrapper therefore does not change
  the preflight on the v0.4.22 code. Decision: no code change for ④; the
  letter's runtime predates v0.4.20, which made a blocked text-mode
  `--approve` print its reason codes, so the client's next occurrence
  carries its own diagnosis. Note for the user: the probe opened the real
  approval dialog on this machine twice for a few seconds; nothing was
  approved and the throwaway archive is outside the repository.
- Observation that does explain a wrapper-only difference: a command string
  re-quoted through another shell layer (for example `powershell -Command
  "..."` carrying quoted arguments) loses its quotes and reaches the CLI as
  split tokens, which the CLI reports as `cli_arguments_invalid` without
  echoing values. A scriptblock keeps tokens intact, so this is not the
  letter's shape, but it is the nearest reproducible way to get a
  wrapper-only refusal.

## Unit U3 (LR-06a): create-draft bound to a claimed work session

Scope decision: LR-06 integrates thirty pending writer paths, and each
integrated writer so far carries four modules and several test modules. The
v0.4.23 unit integrates the most-used native writer, `create-draft`, through
one reusable module (`work_session_native_write.py`) that the other native
single writers can adopt one by one; the remaining paths keep their pending
targets in the coverage manifest.

Design:

- Fresh writes only. `create-draft` gains `--client-app-ref`,
  `--task-route-ref` and `--work-session-ref`; with any of them the draft
  must be an AI-assisted/generated draft with exactly one of `--dry-run` or
  `--approve`, and the command runs inside the session service's held
  archive writer lane (`work_session_service._write`: lock, runtime guard).
- Ownership is verified read-only by the existing
  `_require_actor_selection_for_write_held` (registered app, retained task
  route, currently claimed session, no pending operation) and frozen into a
  `NativeWriteScope` whose digest covers the session binding, the task route
  and the claim ref. The actor image and registry generation are kept for
  compare-and-swap but deliberately excluded from the digest, because the
  operation itself changes them and an exact replay must reproduce the
  reviewed plan.
- The scope digest is frozen into the reviewed fidelity plan
  (`work_session_scope_sha256` in the plan authority, absent for sessionless
  plans, so every existing plan digest is unchanged) and therefore into the
  native dialog's plan binding. The review binding codes are unchanged: the
  service recomputes the same three codes for the claim's context, and the
  plan digest already carries the session.
- After the dialog and before the claim is published, the scope is
  recomputed and must match; the claim publication records the operation as
  pending on the actor (`kind: create_draft`, plan and context digests); the
  succeeded finalizer replaces it with the completed selector under CAS.
  `work_session_actor` learns the `create_draft` operation kind.
- The draft receipt carries `work_session_binding` (the content-free binding
  document) and `work_session_scope_sha256` as paired optional fields; both
  receipt schemas, the private receipt shape validator and the
  approval-integrity validator accept exactly that pair, and the mint-time
  verifier recomputes the plan with the stored scope digest. Results carry a
  content-free `work_session` block; no label, reviewer id or path is
  echoed.
- Refusals before any dialog: missing session ref
  (`work_session_task_context_required`), a session of another task
  (`work_session_task_context_mismatch`), a pending operation on the actor
  (`work_session_original_operation_pending`), both modes or a human draft
  (`work_session_native_write_mode_required` / the generic mode conflict).
- Coverage manifest: `create-draft` becomes `session_integrated` with
  `test_v0423_create_draft_session` as evidence (6 integrated, 29 pending,
  20 exempt of 56); the counts pinned by the release-doc tests move at the
  bump. MCP exposure of the session refs for create-draft is not part of
  this unit.

Evidence: `tests/test_v0423_create_draft_session.py` (4 tests: session-bound
preview and approve with receipt attribution, actor completion, mint-time
verification and idempotent replay; refusals without a dialog; the scope
helpers' CAS and pending guards; the coverage gate). Regression cohort
(every v0.4.20 work-session, source-intake, local-recovery, git-backup,
session and invocation module, capability availability, the capability
matrix docs, letter 137 approval integrity, the v0.3.313 fidelity tests,
the exact operation manifest, predecessor surfaces and the private objet
metadata index): 1,224 tests, one pin moved — the coverage-gate test that
used `create-draft` as its example of a writer without session refs now
uses `promote`.

## Client boundary

Nothing here sets any letter's `resolved_in`. Client-side confirmation of ②
needs one create-draft over a real binary original on the client's archive
with `--source-fidelity faithful_summary` or `sanitized_derivative` after the
v0.4.23 update; ④ needs the client's rerun on v0.4.20 or later, which prints
the blocking reason codes in text mode.
