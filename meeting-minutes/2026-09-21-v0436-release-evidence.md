# v0.4.36 release evidence and client boundary

Date: 2026-09-21 (Korea Standard Time).

Release steps from the merge onward were executed by Codex after a handoff,
solo and sequential. The [implementation record](2026-09-21-v0436-letter-168.md)
and [decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-21-v0436-letter-168.md)
describe the product changes. Only synthetic archives and development repositories
were used. Customer workspaces and installed runtimes were not changed.

## Source and candidate verification

- [PR #130](https://github.com/mow-coding/zettel-kasten/pull/130) merged candidate
  `55b74941b7e4972b8e64ac44c188a12fb7426ee4` to
  `a1cce66d2f63bac01aa86409a2437947255c3e12`.
- Candidate and merge have identical tree `9c3f57bfc3b8683dd312583b2b3cd8a1cbdad0bc`.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35531677443)
  passed all 14 jobs. Earlier failing assertions were corrected to match the
  new behavior while retaining negative coverage; the failed run was not called a pass.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35536751308)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35536794000)
  passed their configured fast gates. They did not repeat the candidate matrix.
- Annotated tag `v0.4.36`, object `b90af774e9165df91953a2d3fd58a1bf0e725346`,
  peels to the exact merge above; the remote target was independently checked.

## Exact-tag wheel verification

The initial local supplement failed after 2522.195 seconds: its runtime journey
exhausted a 2400-second limit during repair resume. That run remains failed,
and local performance root cause is unconfirmed. See the
[environment decision](2026-09-21-v0436-release-artifact-verification.md).

The [one-off Windows verification](https://github.com/mow-coding/zettel-kasten/actions/runs/35539848491)
then passed the complete **unmodified committed checker**, including its original
1200-second runtime limit. Workflow commit `70fc7c6840e217cd95fe833b7979025cb0b4a7ef`
is the orchestration revision; the product checkout was pinned to the exact merge
`a1cce66d2f63bac01aa86409a2437947255c3e12`. Source commit, tree, annotated tag,
peeled target and clean checkout were checked before preserving the wheel.

The run's `wom-v0436-exact-tag-wheel` artifact contains the wheel,
`wheel-verification.json` and `source-provenance.json`. Job success, `ok: true`,
`checker_modified: false`, source identifiers, SHA-256 and size were checked again
after downloading. The wheel that passed was uploaded unchanged; it was not rebuilt.
The temporary workflow is not part of this evidence PR or main's CI configuration.

The installed CLI/MCP entrypoints report 0.4.36; the two MCP inventories agree
(137 tools). Installed link, recovery, batch, truth-contract and runtime-journey
checks passed, including actual update, no-op, source/ref drift refusal,
interrupted repair and fresh-process resume. Runtime skill lifecycle and strict
Doctor on the checked-in synthetic archive passed. This does not demonstrate
every new grant-enabled command end to end in a customer's environment.

## Public artifact

[WOM-kit v0.4.36](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.36)
was published at `2026-09-20T22:16:31Z` (2026-09-21 07:16:31 KST),
after draft asset digest and size matched the verified file. It is neither draft
nor prerelease and has exactly one wheel.

| Evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.36-py3-none-any.whl` |
| Size | 3340372 bytes |
| SHA-256 | `df925a87dc45cab4f228726b91ba9f481797049ae4291ebca77dc1dfa0f99941` |
| Verified resources | 173 |
| Resource bytes | 751696 |
| Scanned text-like wheel members | 319 |
| Scanned text-like bytes | 18171790 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

An unauthenticated API request confirmed the public state and asset identity.
An anonymous download reproduced the exact digest and size.
Two fresh CPython 3.12 environments then passed the checked verifier (exit 0):
one installed the anonymous local download, the other installed the exact public
URL with its SHA-256 fragment and isolated pip configuration. Both returned
`archive 0.4.36` in a new process, passed `pip check`, verified all 173 resources
(751696 bytes, zero mismatches), and matched the PEP 610 wheel digest.
The public-URL environment returned `exact_public_release_wheel_verified` from
`public_github_release`; the local-file environment correctly returned
`running_distribution_not_from_exact_public_release_wheel`.

## Customer acceptance and remaining work

L168-01 through L168-05 remain open for customer acceptance. Publication does not
prove successful upload, faster finalization, archival, or a dialog-free updater
in the customer's own session. The no-dialog updater grant has synthetic broker
coverage; full updater-with-grant acceptance remains explicit follow-up work.
The newer project/session-close feedback is separately triaged and is not claimed
as fixed by this release. Functional backlog has no promised future version.

The reply is provided to the user as a file; the developer does not send it.
The [engineering-process decision](2026-09-21-engineering-process-decision.md)
is included as requested, with a current-scope correction; the broader operating
documents remain separate local work. Task-owned verification environments and
temporary branches are removed after evidence is preserved. The verified wheel
is retained in the ignored release output directory. Unrelated local work stays intact.
