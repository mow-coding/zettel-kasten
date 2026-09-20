# v0.4.36 release artifact verification environment

Date: 2026-09-21. Scope: one release, synthetic archives only.

The corrected candidate passed all 14 jobs in run 35531677443. PR #130 merged to a1cce66d2f63bac01aa86409a2437947255c3e12, with the candidate's identical tree 9c3f57bfc3b8683dd312583b2b3cd8a1cbdad0bc. Annotated tag v0.4.36 targets that commit.

A local supplement check failed after 2522.195 seconds. Its runtime journey exhausted the 2400-second outer limit during repair_fresh_resume, after repair_cut_validation passed. Product completion remains unknown for that run. It is not successful release evidence.

Several completed local stages took roughly two to three times the candidate CI durations: initial update 716.906 versus 212.391 seconds, no-op 189.828 versus 75.782, source drift 244.670 versus 80.297, and repair preparation 445.610 versus 142.687. This is an observed environment difference, not a proven root cause. The candidate's full repair resume passed in 203.640 seconds on Windows CI.

## Operational decision

Use a one-off workflow branch to build and run the complete, unmodified installed-wheel checker on Windows against the exact release tag. Its runtime limit remains the committed 1200 seconds. Preserve the wheel that actually passed, its verification JSON, and a machine record of the source commit, tree, annotated tag, digest, size, and workflow run.

The workflow definition is on a temporary branch, but source checkout is pinned to the release merge. It verifies both tag object and peeled target before building, and checks the checkout is clean afterwards. No main workflow, product source, approval policy, or existing tag is modified by this operational branch. It is not the future beta-channel implementation.

Download and compare the preserved wheel and evidence before creating a draft release. Then retain the original draft-asset comparison, anonymous download, two fresh installations, evidence PR, reply, and cleanup steps. Record the unsuccessful local run and the actual successful verification environment honestly. No customer result is inferred.

Status at preparation: workflow not yet run; no public v0.4.36 release exists. Local performance root-cause diagnosis remains a follow-up item.

## Final outcome — 2026-09-21

Run 35539848491 passed the unmodified checker against the pinned release merge.
The preserved wheel and machine provenance were independently downloaded and
matched; the same wheel was published as v0.4.36. The local timeout remains a
failed observation, with performance diagnosis still pending. See the
[release evidence](2026-09-21-v0436-release-evidence.md) for exact identifiers,
artifact hash, public checks and customer acceptance boundaries.
