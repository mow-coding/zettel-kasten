# Decision: work like the professional open-source projects of our category (2026-09-21)

> Later scope correction, 2026-09-21: the user first deferred release
> execution to research and document a shared Claude/Codex development process,
> then explicitly resumed v0.4.36 release work after that document phase.
> The new operating documents remain local and will be published separately.
> This record is self-contained and does not link to unpublished local files.
> The earlier four-full-CI-run description and blanket 4-to-8 shard prescription
> are not current verified facts: main/tag already use fast gates, and measured
> bottlenecks must guide further CI changes. Weekly means reviewing whether a
> stable release is needed, not publishing unconditionally. No automation was
> activated by this record. Functional follow-ups do not have a committed
> v0.4.37 delivery promise; process improvements take priority next.

Date: 2026-09-21 ~03:00 KST. Recorded by Claude Opus 5 during the v0.4.36
candidate CI (PR #130).

## What the user decided

After seeing that one release costs about 3.5 hours (four CI runs of ~95
minutes, a 30-minute installed-wheel check, hand-written evidence) and that
every client letter has been turned into a full public release, the user
said: "나는 우리 프로젝트와 비슷한 카테고리의 오픈소스 프로젝트들을 다루는
프로들처럼 일하고 싶어. 이런걸 진작에 했어야 했는데."

The category: a local-first personal archive operated by an AI under human
approval and receipts — the working peers are restic / Borg / git-annex
(verified archival), Terraform (plan → approve → apply with bound digests),
rclone (provider transports), Homebrew / pip (self-updating CLI), and the MCP
server ecosystem.

## What that means in practice (the v0.4.37 process release)

1. **Merge and release are separate.** A fix merges to `main` as soon as the
   fast PR tier passes. Public stable releases are cut on a cadence (default:
   weekly, or on demand when a client needs one), not per letter.
2. **Tiered CI.** PR tier: docs-only changes skip the test shards; a tree
   already verified by the candidate run is not re-run on the main / tag
   push; Windows shards 4 → 8. Nightly / tag tier: the installed-wheel
   journey, the full matrix, the scale gates.
3. **Beta channel.** Every merge to `main` builds and publishes a pre-release
   wheel automatically (`vX.Y.Z-beta.N`) with its digest; beta clients update
   from it within minutes; the stable release keeps the anonymous download,
   fresh-venv install and new-process checks.
4. **Evidence from machines.** Release notes drafted from PR labels; the CI
   run, the tag and the artifact digest are the evidence; the hand-written
   release-evidence minutes become a short pointer. Decision logs and
   meeting minutes stay for decisions and corrections (the AGENTS mandate).
5. **Letters become issues.** The operator-feedback body format becomes a
   GitHub issue template; each letter's items get labels and a milestone so
   "carried to vX" is tracked by the tracker, not by memory.

## Boundaries that do not change

Synthetic fixtures only; no client data; the exact-approval contract; the
stable release's public-artifact verification; every decision recorded.

## Next

v0.4.37 opens with items 1–3 (CI configuration and the beta-build workflow),
then 4–5. The user chooses the stable cadence; weekly is the default until
he says otherwise.
