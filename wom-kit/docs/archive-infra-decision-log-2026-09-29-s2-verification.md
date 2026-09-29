# Decision log: the additional-verification items S2-U01..U25 (2026-09-29)

## Context

The 2026-09-28 feedback audit listed 25 verification items (S2-U01..U25) taken
from earlier sessions' unverified claims. Every item now has a synthetic test on
the example archive (`tests/test_s2_verification_*.py`), and the gaps those
tests exposed were fixed in the same release where the fix was small and inside
an existing contract. The owner delegated the remaining design on 2026-09-25;
the recommendations below are recorded as delegated.

## Decisions

1. **Linked targets show a title or an exact reason (S2-U06).** A
   `read-zettel` overview edge preview carries `target_title` for a zet target,
   read from the archive index and never from the target file, and always a
   `target_label_state` from a fixed list. An objet has no reviewed human label,
   so the preview says `objet_has_no_human_label` instead of inventing one from
   a private filename.
2. **A handoff never reads as complete while drafts wait (S2-U15).**
   `session-handoff-checkpoint` returns `inbox_attention` and, when unpublished
   drafts exist, a `next_safe_actions` line saying the checkpoint did not publish
   them. The state digest is unchanged, so existing approvals stay valid.
3. **The documented example obeys its own contract (S2-U10, S2-U16).** The
   `ai_assisted` `create-draft` example in the skill carries `--abstract`,
   `--facet`, `--source-fidelity` and `--fidelity-source-object-id`, and the
   publish row names `zet-quality-check` between `create-draft` and `mint-zet`.
   A test now fails if either regresses.
4. **`draft-disposition --approve` reaches the dialog (S2-U24, A15).** Its
   approval context carried unsorted `review_binding_codes`, so every official
   approve raised `exact_human_approval_context_invalid` before the dialog; the
   existing tests had injected the context. Fixed by ordering the codes.
5. **Not built: a canonical hold (S2-U24).** No command places a canonical zet
   on a reversible hold; `draft-disposition` refuses a canonical id. Recommended
   design, pending the owner's reading: a `canonical-hold` lifecycle event
   (hold, review, release) appended beside the mint receipt with a stable id and
   a policy reason, never moving or editing the canonical file, and reported by
   `status-board` and `read-zettel`. Retirement stays the only removal path.
6. **Kept as boundaries, not bugs.** `authoring-conventions` is advisory
   (S2-U12); `status-board` counts `canonical_lifecycle_metadata_missing` as a
   review signal because legacy imports carry no mint block (S2-U14); a link
   role changes only through receipt lookup, revert and re-link (S2-U19/U22);
   the two-count index discrepancy has no reproducing fixture and stays an
   observation (S2-U08).

## Boundaries

- Every check is synthetic (example archive copy, injected dialog and key). A
  customer's own archive and the physical Windows dialog were not exercised.
- Exact-approval writes that stay fixed-closed without the native dialog
  (`migrate --target base-link-types --approve`) were verified through their
  dry-run plans only.
