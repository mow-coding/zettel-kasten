# v0.4.35 release evidence and client boundary

Date: 2026-09-20 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The scope and unit decisions are in
the [implementation record](2026-09-20-v0435-letter-167.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-20-v0435-letter-167.md)
and the acceptance register (L167-01).

## User intent and execution boundary

v0.4.35 is the beta letter 167 hotfix: the public-history rewrite of
2026-09-20 left the client's source mirror unable to fast-forward
`origin/main`, and `project-version-update` refused the update saying only
"fetch failed / tag missing". The release makes a refused fetch name its
rejection kind and the remote's own tag and main observation, and accepts
a rewritten origin main only under `--affirm-origin-main-rewritten`.
Development used synthetic upstream and mirror repositories and the
injected runtime seams only; the client's letter was read from its
feedback ledger; no client runtime, archive, workspace, mirror,
credential, provider configuration or shared PATH installation was read
or changed by this release execution, and no client identifier appears
in any repository file.

## Reviewed source and CI

- [PR #128](https://github.com/mow-coding/zettel-kasten/pull/128)
  squash-merged exact head `ec086dba` into
  `5858db1afe95b6ae0b156c9485b1d39361c6208c`. The merge commit's tree
  `500f0db7595e1ab29b3f92b17ff2568aae947d63` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35501895226)
  passed all 14 jobs (attempt 1 after one test-only correction: the approve-path test gained the Windows-only skip every approve-path CLI test carries).
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35506025782)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35506046379)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.34 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`5858db1a`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (748430 bytes),
318 wheel members scanned (18110359 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.35; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.35` has tag object
`2d58949485f8af99a4e682fa22b4d51eb4e5bd23` and remote peeled target
`5858db1afe95b6ae0b156c9485b1d39361c6208c`, equal to the main head.

[WOM-kit v0.4.35](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.35)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-20T11:29:46Z (2026-09-20 20:29 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.35-py3-none-any.whl` |
| Size | 3324064 bytes |
| SHA-256 | `a9fe67eef113fdc731357152f22178cf312affc7ead2c3a02652b33a7f7d48ec` |
| Verified package resources | 173 |
| Verified resource bytes | 748430 |
| Scanned text-like wheel members | 318 |
| Scanned text-like bytes | 18110359 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.35` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.35")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0435-letter-167` holds no unmerged product change
(the released tree equals the branch tree) and is removed after this record
merges; the untracked supplement checker copy is deleted; the supplement
wheel stays under the ignored `wom-kit/dist-v0435/` directory and is never
committed.

Public release, local installed verification and source tests do not set
letter 167's `resolved_in` and do not close L167-01, which needs the
client's own run: the v0.4.35 bootstrap, a dry-run showing
`fetch.rejection_kind: non_fast_forward` and `origin_main_rewritten: true`,
and the approved update with `--affirm-origin-main-rewritten` reporting the
before and after ids. The letter 167 reply draft explains the cause (the
public-history rewrite), points the client at v0.4.35 and lists the two
commands; the user sends it. The v0.4.35 list of the letters 164+165 reply
is carried to v0.4.36.

## Decision (2026-09-20 ~21:20 KST): no GitHub Support purge request

After the release the user asked what exactly the public-history rewrite had
removed. Answer given: two strings only — the user's Windows account folder
name (inside absolute paths in decision logs and minutes) and the client's
identifier (reviewer id, workspace folder name, prose mentions); no password,
token, key or credential. Checked read-only: the current history holds 0
occurrences; one pre-rewrite commit (the old v0.3.170 tag target) still
resolves anonymously by its commit id and its old file still shows the account
folder name once, so the strings stay reachable by anyone holding an old
commit id until GitHub's own garbage collection. The user decided that this is
acceptable and that the support request drafted in
[2026-09-20-github-support-request-draft.md](2026-09-20-github-support-request-draft.md)
is not to be sent. A GitHub Support form had been opened in the user's browser
to prepare it; nothing was entered or submitted, and the tab was closed.
