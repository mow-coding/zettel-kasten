# v0.4.26 release evidence and client boundary

Date: 2026-09-18 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the reproduction, the
hotfix, the bump and every release step, under the user's standing approval
to run the release train without re-asking; the user approved the live
reproduction and the hotfix release explicitly. The diagnosis and unit
decisions are in the
[hotfix record](2026-09-18-v0426-target-details-hotfix.md), the
[decision-log amendment](../wom-kit/docs/archive-infra-decision-log-2026-09-18-v0426-target-details-navigation.md)
and the acceptance register (UF-03).

## User intent and execution boundary

v0.4.26 fixes the native approval dialog's "대상 자세히 보기" button on
Windows 11: a late navigation confirmation keeps the page inert instead of
cancelling the dialog as `exact_human_approval_native_call_failed`.
Development used synthetic labels on a real task dialog and fake-dialog
tests only; no archive, no client runtime, workspace, feedback ledger,
credential, provider configuration or shared PATH installation was read or
changed by this release execution.

## Reviewed source and CI

- [PR #112](https://github.com/mow-coding/zettel-kasten/pull/112)
  squash-merged exact head `d5fbc6b9` into
  `e998852d73e84603f595452430966e7c7b3efd99`. The merge commit's tree
  `96dc82e5b3ac2df5ca0b6b1dbb156952308d3920` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35317937846)
  passed all 14 jobs on the first run with no rerun and no correction
  commit.
- Main and tag CI runs on `e998852d` passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.25 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`e998852d`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (731,123 bytes),
307 wheel members scanned (17,565,527 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.26; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.26` has tag object
`53333070981e56bf25020b2eb348588e84fb14e0` and remote peeled target
`e998852d73e84603f595452430966e7c7b3efd99`, equal to the main head.

[WOM-kit v0.4.26](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.26)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-18T14:17:19Z (2026-09-18 23:17 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.26-py3-none-any.whl` |
| Size | 3,200,233 bytes |
| SHA-256 | `fc61406459927608dcd75981485211b65434224fc232994ff61b3e3bdb2e4043` |
| Verified package resources | 169 |
| Verified resource bytes | 731,123 |
| Scanned text-like wheel members | 307 |
| Scanned text-like bytes | 17,565,527 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.26` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.26")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Client verification of v0.4.25 (same day)

The client's report of its v0.4.25 run reached the maintainer while this
release was in CI: the archive-root recovery and update succeeded exactly as
the v0.4.25 record predicted, the session permission mode cut eleven writes
to two dialogs, and the client stated that letters 157 through 162 may be
closed. The acceptance register carries that verification on SP-01, UF-01,
UF-02 and LR-01, and lists the follow-ups carried to v0.4.27. The report
also confirmed, on the client's own dialog, the "대상 자세히 보기" failure
that this release fixes.

## Cleanup and remaining work

The work branch `claude/v0426-target-details-navigation` and its worktree
hold no unmerged product change (the released tree equals the branch tree)
and are removed after this record merges; the untracked supplement checker
copy is deleted after this record; the supplement wheel stays under the
ignored `wom-kit/dist-v0426/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. UF-03 closes only when the client's
operator presses "대상 자세히 보기" on v0.4.26 and sees the list page. The
dialog's foreground-window ownership stays recorded as deferred.
