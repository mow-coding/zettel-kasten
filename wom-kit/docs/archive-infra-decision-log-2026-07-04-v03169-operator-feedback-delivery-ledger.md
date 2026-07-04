# Decision Log — v0.3.169 Operator-Feedback Delivery Ledger + Batched Mark-Delivered

Date: 2026-07-04
Batch: v0.3.169 (implements the LOCKED spec "Operator-Feedback Delivery Ledger":
read-only `operator-feedback-ledger` + approval-gated
`operator-feedback-mark-delivered`).
Anchor tree at spec authoring: HEAD `b5e6a258` (v0.3.168), tree clean.
Release action: working tree only — no git commit/tag/push. Never touches a real
archive or `C:\Users\mylifeisbusy\zettel-kasten-basoon`; all archive fixtures live
in temp dirs.

This log records the design decisions and, per the AGENTS.md decision-log mandate,
each of the six critique required-changes with the grounded fact that drove it and
how it was folded in.

## Source

basoon 3rd letter §3 (verified in intake): 60+ operator-feedback records carry a
`status` field, but there was (1) no read-only ledger/board aggregating delivery
status + a pending list; (2) no delivery-boundary commit — status was hand-edited
one record at a time via `operator-feedback-record --status`; (3) the running
tracker mixed delivered/pending so the operator lost "how far did I deliver". This
was already documented as the v0.3.149 "Still Future: feedback status board".

## Prime directives (highest priority)

- **Privacy — status + ids only.** The on-disk record holds `feedback_ref` and
  `title` (writer lines ~3394/3396). Every ledger/mark-delivered result and receipt
  projects only feedback id + status + safe timestamps; the raw record dict is never
  spread into output.
- **Truth — metadata lifecycle only.** `delivered` is a metadata stamp at the same
  trust level as the existing `--status delivered`. No external submission is
  performed; `external_submission_performed` stays `false`.

## Design decisions

- **D1 ledger is read-only, requires `--dry-run`, projects a curated view.** Mirrors
  the `archive_status_board` precedent of building a curated `item`, not returning the
  loaded frontmatter. Reuses `OPERATOR_FEEDBACK_STATUSES`, `OPERATOR_FEEDBACK_DIR`,
  and `safe_archive_glob`. Pending list = records with `status == 'draft'` (the only
  not-yet-delivered state).
- **D2 mark-delivered reads-then-mutates, does NOT route through the record writer.**
  Transitions only `draft -> delivered`, stamps `delivered_at` + `reviewed_by` +
  `updated_at`, writes atomically per record + one batch receipt. Idempotent by the
  draft-only filter. `--only <id>` scopes to a single record.
- **D3 no-overclaim documented everywhere.** Lifecycle doc, release note, matrix
  rows, and receipt all state `delivered` = "operator marked it delivered", not
  proof of external delivery or human receipt.

## Critique required-changes (all folded in)

1. **`delivered_at`/`acknowledged_at` did not exist (grep = 0 at HEAD).** FIX: the
   ledger treats both as strictly optional and never presents the boundary as
   authoritative. The delivery boundary falls back to `updated_at` of delivered
   records when `delivered_at` is absent, and the ledger reports
   `delivery_boundary_stamped_count` separately. Documented that records delivered
   via the old `--status` path have no `delivered_at`.

2. **Writer-reuse trap: `operator_feedback_record` rebuilds the dict from CLI args
   and never merges on-disk (same pattern as `approval_handoff_record`).** FIX:
   mark-delivered does NOT call `operator_feedback_record()`. It reads the existing
   YAML via `load_yaml`, preserves `feedback_ref`/`title`/`related_releases`/
   `resolved_in`/`body_managed_by_this_record`/`external_submission_performed`
   verbatim, mutates only status + `delivered_at` + `reviewed_by` + `updated_at`, and
   writes atomically. This keeps the shipped schema's 11 required fields intact.

3. **Schema conformance on the mutated record is not covered by the existing
   conformance test.** FIX: mark-delivered re-runs `validate_schema(record,
   "operator-feedback.schema.json")` on the mutated record BEFORE writing (a failing
   record is skipped, never written). A new test loads the post-approve
   `ops/feedback/<id>.yml` and asserts zero schema issues, proving all 11 required
   fields survived and `delivered_at` did not break anything. The release gates do
   not run schema validation, so this is pinned by pytest.

4. **Runtime privacy leak is caught by no gate — only pytest.** FIX (projection):
   the ledger builds a projection of `{feedback_id, status, delivered_at?,
   acknowledged_at?, updated_at}` and never spreads the raw record; mark-delivered's
   result, `would_change`, summary, and receipt carry only feedback id + status +
   timestamp + reviewer. Tests seed a record whose `feedback_ref` AND `title` carry
   distinct secret-ish markers and assert BOTH are absent from `json.dumps(ledger)`,
   `json.dumps(mark_delivered_result)`, AND the on-disk batch receipt. FIX (id
   re-sanitization): because records are documented as hand-editable one at a time,
   the `feedback_id` read back from disk is re-run through `safe_operator_feedback_id`
   in both the ledger projection and mark-delivered before it is ever echoed; on
   failure it falls back to the safe on-disk file stem, mirroring the `--only`
   sanitization. A hand-authored record whose internal `feedback_id` is a URL/token
   therefore cannot leak that value into the pending list, mark-delivered output, or
   the receipt — a regression test asserts exactly this.

5. **Malformed record fail-unsafe: `load_yaml` -> `yaml.safe_load` raises
   `yaml.YAMLError`; the `archive_status_board` precedent catches only `OSError`.**
   FIX: both commands wrap each per-record read in `except (OSError, yaml.YAMLError)`
   AND guard `isinstance(loaded, dict)`, counting bad files into an `unreadable`
   bucket and skipping them. mark-delivered enforces per-record atomicity — a
   mid-batch bad record is reported and skipped, never half-writing others. A test
   seeds one valid draft + one corrupt `.yml` + one list-valued `.yml` and asserts the
   ledger reports two unreadable while aggregating the valid one, and mark-delivered
   transitions the valid draft while skipping the corrupt files with a sane return
   code and the corrupt bytes untouched.

6. **Overclaim / status semantics.** FIX: the receipt preserves
   `external_submission_performed: false` and adds `delivery_is_metadata_only: true`
   (mirroring the existing `body_managed_by_this_record: false` honesty pattern). The
   lifecycle doc's `delivered` meaning and the release note state plainly that
   `delivered` means "the operator marked it delivered", not external submission or
   human receipt. When flipping the v0.3.149 "A feedback status board" Still-Future
   item to shipped, the OTHER Still-Future items (real submission to a maintainer
   channel, cross-archive relay, inbox migration, issue/release-note linking) are
   kept intact.

## Open-question answers (confirmed at HEAD)

- The record on disk holds `feedback_ref` + `title` but not the body/URLs/paths
  (rejected at write time). Leak risk is specifically ref + title; closed by
  projection + tests asserting both markers absent.
- `OPERATOR_FEEDBACK_STATUSES` already contains `delivered` and the pending state
  `draft`; reused, not redefined. Added `OPERATOR_FEEDBACK_PENDING_STATUS = "draft"`
  as a named constant for the draft-only filter.
- Idempotence holds because the draft-only filter runs before transitioning; a
  second `--approve` marks nothing (`delivered_count: 0`, no record rewritten).
- Version files bumped in lockstep: `pyproject.toml` and `src/wom_kit/__init__.py`
  to `0.3.169`. The test-suite version assertion reads `wom_kit.__version__`, so no
  hardcoded version string in `tests/test_cli.py` needed editing.
- The release gates (`check_public_privacy`, `check_release_readiness`) scan only
  git-tracked public files, not command output or record correctness, so every
  privacy/schema/idempotency/fail-safe guarantee for these two commands rests on the
  pytest suite; the test list is load-bearing and was strengthened accordingly.

## Pre-release review findings (fixed in the working tree before commit)

7. **Delivery-boundary receipt could be overwritten by a same-second batch.**
   The receipt filename was `delivery-batch.<YYYYMMDDTHHMMSSZ>.json`, keyed on the
   whole-second UTC timestamp alone. `write_text_atomic` does an unconditional
   `replace`, so two `--approve` commits within the same wall-clock second (e.g. the
   sanctioned per-record `--only` workflow run in a loop) collapsed to ONE file and
   the earlier batch's audit receipt was silently destroyed — even though the record
   transitions themselves were correct. FIX: the filename now carries a per-batch
   content digest (`sha256_json_hex` of the sorted delivered ids + reviewer +
   timestamp + `--only` scope), mirroring the `mint_batch`/`retire_draft_batch`
   receipt paths, so each batch is durably and uniquely named:
   `delivery-batch.<timestamp>.<batch-digest>.json`. The digest is also recorded in
   the receipt body (`batch_digest`, added as an optional schema property). A
   regression test freezes the clock, delivers two records one at a time via `--only`
   in the same second, and asserts BOTH receipts survive with the correct contents.

8. **A no-op `--approve` still wrote a zero-delivery receipt.** The receipt-write
   branch was gated only on `approve and not blockers`, independent of whether any
   record transitioned, so an idempotent second approve (once no drafts remain) wrote
   a fresh `delivery-batch.*.json` with `delivered_count: 0`. The record transitions
   were idempotent but the receipt side effect was not; empty boundary artifacts
   accumulated. FIX: the receipt is written only when at least one record actually
   transitioned (`approve and not blockers and delivered_ids`); a no-op approve
   returns `receipt_path: null` and writes nothing. The idempotency test now asserts
   the receipt count does not grow on the no-op re-run and that `receipt_path` is
   `null`.
