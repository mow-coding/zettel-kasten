# Archive infrastructure decision log — 2026-09-20, v0.4.35 (beta letter 167: the updater and a rewritten origin main)

Executing model: Claude Opus 5, solo and sequential, under the user's
standing approval. No client archive, runtime, workspace or ledger was read
or changed; the client's letter was read from its feedback ledger; every
fixture is synthetic.

## What the letter established

The client's v0.4.30 → v0.4.34 update was refused after a 46-second fetch
with `The atomic configured-origin fetch failed` and
`observation_reason_code: project_target_tag_missing`, although the tag was
on the remote. The client reproduced the cause read-only in the source
mirror: `git fetch --atomic --no-tags origin refs/heads/main:refs/remotes/origin/main …`
is rejected with `main -> origin/main (non-fast-forward)` because the
remote `main` no longer descends from the mirror's `origin/main`.

## Cause

This is a direct consequence of the approved public-history rewrite of
2026-09-20 02:00 KST ([record](archive-infra-decision-log-2026-09-20-public-history-rewrite.md)):
every commit id changed, so a mirror that had fetched the pre-rewrite `main`
cannot fast-forward. The updater's fetch is deliberately non-forced (a
defence against a rewritten upstream), so it refused — correctly — but it
reported only "fetch failed" and "tag missing locally", because the bounded
Git runner never captures stderr and no remote read existed on the failure
path. The rewrite record did not anticipate the client mirror; that is a
planning omission of the rewrite, recorded here.

## Decisions

1. **Reverting the remote is not an option.** Restoring the pre-rewrite
   `main` would republish the removed private identifiers. The updater
   learns to name and, under an explicit affirmation, accept the rewrite.
2. **Fetch diagnosis without stderr.** When the atomic fetch fails, the
   updater runs one `ls-remote` (is the remote reachable, is the exact tag
   there, what is its `main`), then checks whether the local `origin/main`
   is an ancestor of the remote `main` — using the objects the rejected
   fetch usually left in the store, else by fetching the exact tag into a
   private probe ref (`refs/wom-kit/probe/<tag>`, removed afterwards; never
   `refs/tags`, so a later dry-run's local-tag view is unchanged). The
   result's `fetch` block carries `rejection_kind` (one of
   `non_fast_forward`, `remote_unreachable`, `target_tag_missing_on_remote`,
   `ref_update_rejected`), `remote_reachable`, `target_tag_on_remote`,
   `origin_main_before_fetch`, `origin_main_remote_sha`,
   `origin_main_rewritten`. Commit ids are public; no stderr, URL, path or
   credential value is echoed.
3. **Reviewed acceptance: `--affirm-origin-main-rewritten`.** With the
   affirmation the one fetch uses `+refs/heads/main:refs/remotes/origin/main`
   (the tag refspec is never forced, atomic and `--no-tags` stay); the
   dry-run and the result report `fetch.main_ref_forced_update_affirmed`,
   the result reports `origin_main_before_fetch` / `origin_main_after_fetch`
   and `origin_main_rewrite_accepted`, and the bound warning code
   `origin_main_rewrite_affirmed` enters the approval context (the plan
   digest covers the whole preview, so the human's one dialog binds the
   affirmation). Without it a rewritten `main` is refused as before, now
   with the blocker naming the flag and the next step. The tracking ref
   moves before the dialog, as every fetched ref does; the before id is
   reported for a manual `git update-ref` if the operator changes their
   mind before approving.
4. **No receipt schema change.** The update receipt is a static document
   built from the transaction intent; the acceptance is evidenced by the
   result and by the claim's bound warning code.

## Carried

The v0.4.35 list of the letter-165 reply (`max_writes`, revoke, session
refs, select-all, reviewed re-PUT, letter 164 ⑧, 8b) moves to v0.4.36;
this release is the hotfix alone.
