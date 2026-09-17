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

## Client boundary

Nothing here sets any letter's `resolved_in`. Client-side confirmation of ②
needs one create-draft over a real binary original on the client's archive
with `--source-fidelity faithful_summary` or `sanitized_derivative` after the
v0.4.23 update; ④ needs the client's rerun on v0.4.20 or later, which prints
the blocking reason codes in text mode.
