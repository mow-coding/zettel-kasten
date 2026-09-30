# Archive infra decision log: letter 178 (2026-09-30)

Status: implemented for v0.4.54 under the owner's standing instruction to
finish every implementable item before the reply.

## What the customer saw

The approved update to v0.4.52 returned `ok: true` and
`updated_restart_required`, and also `post_update_attention_required: true`
with `durable_result_delivery_acknowledged: false`. The helper AI missed the
warning. Later the v0.4.53 preview (`project-version-update --target v0.4.53
--dry-run`, run with an isolated v0.4.53 runtime) stopped with
`project_version_update_terminal_cleanup_outcome_unknown` and the instruction
to report to WOM development. The customer could therefore not install the
releases that answered letter 177.

## What was reproduced (real CLI, synthetic project)

- A successful update acknowledges its result delivery in a clean project.
  `lifecycle: active, terminal: false` in the result is a snapshot taken before
  cleanup and is also seen on clean runs; it is not a failure sign.
- One unrelated operation journal in the project that fails the strict reader
  (a torn last line from a killed process, a copied project, a clock step)
  made the post-acknowledgement re-check raise. The CLI caught it silently and
  reported delivery as not acknowledged: the customer's first symptom.
- A delivery renamed to `display-pending` but never finalised made the next
  preview look clean while the approve failed with a generic error.
- The advised command (`project-version-update --resume`) lacked
  `--affirm-external-writers-quiescent` and `<archive-root>`, so copying it
  failed with `project_version_update_quiescence_required`.
- Not reproduced: the exact state that makes the preview return
  `outcome_unknown`. No version binding exists between the handoff and the
  runtime, so a newer runtime does not reject an older handoff by itself; the
  customer's project holds one more kind of leftover that the result did not
  name.

## Decisions

1. The delivery re-check skips journals that cannot be read or belong to
   another root instead of failing. A broken journal cannot carry the
   capability proof a delivery candidate needs, so authentication is
   unchanged (handoff digest, capability, durability and uniqueness checks
   stay).
2. When delivery is not acknowledged the result carries
   `terminal_finalization.result_delivery_failure_code` (fixed literals:
   `acknowledge_failed`, `delivery_boundary_not_released`,
   `delivery_candidate_not_verified`, `delivery_discovery_failed`,
   `delivery_not_attempted`).
3. A pending `display-pending` delivery is named in the preview
   (`outcome_basis: previous_update_result_delivery_pending`) with the exact
   command to run with the project's current launcher.
4. Every `outcome_unknown` result names its branch (`cause_code`) and carries
   a names-free `residue_inventory` (lock present, handoff files present,
   counts of transaction entries, runtime cleanup sidecars and journals), and
   first advises the identifier-free resume with the current launcher.
5. Every advised resume line is the complete, copyable command:
   `archive project-version-update <archive-root> --resume
   --affirm-external-writers-quiescent --format json`.

Unchanged invariants: no domain-writer re-entry, no automatic retry, no
private identifiers on resume, fixed literals only, fail closed on handoff or
reference mismatch, no deletion of control evidence.

## The letter itself

- The request now requires an `author` block (AI product, model, reasoning
  level, source). Placeholders such as `미수집` are refused unless the person
  could not tell either, and the refusal says to ask the person.
- The developer-letter guidance states that the person sees exactly two
  states, `전달 전` and `전달 완료`; an approved compose is the letter, there is
  no further registration step, and an instruction already given is not asked
  again.

## For the customer

First run once, with the project's current v0.4.52 launcher:
`archive project-version-update <archive-root> --resume
--affirm-external-writers-quiescent --format json`, then preview again. If the
preview still stops at `outcome_unknown`, v0.4.54's result names the cause and
the leftover kinds; that result (content-free) is what the next letter should
carry. The customer's own run is not confirmed.
