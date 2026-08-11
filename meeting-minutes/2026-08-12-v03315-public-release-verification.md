# WOM-kit v0.3.315 public release verification

Date: 2026-08-12

Status: released and independently verified

## Scope

This record closes the v0.3.315 work derived from Letters 127 and 128. It
separates implementation, local verification, merge, public CI, tag, Release,
fresh installation, and a disposable update canary. No protected client
archive, provider account, or real user content was changed during this
closeout.

## Merge and public CI

- Implementation PR: <https://github.com/mow-coding/zettel-kasten/pull/60>
- Reviewed PR head: `82ba86a476e689803b72a733c76ffbee8e3ae30e`
- Merge commit: `b078abe807de4cfccecc5d122b4a6ef30450eb63`
- CI run: <https://github.com/mow-coding/zettel-kasten/actions/runs/31520267226>
- CI result: 10 of 10 checks passed, including the required aggregate gate;
  failure and cancellation count were both zero.
- The first PR run exposed five real Windows preservation tests that were also
  selected on Ubuntu. The tests now retain full execution on Windows and use
  explicit Windows selection on Ubuntu. The corrected PR head passed every
  Ubuntu and Windows shard.

After merge, local `main` and `origin/main` both resolved to the merge commit
and the development worktree was clean.

## Tag and Release

- Annotated tag: `v0.3.315`
- Peeled local and remote tag target:
  `b078abe807de4cfccecc5d122b4a6ef30450eb63`
- Release: <https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.315>
- Published asset: `wom_kit-0.3.315-py3-none-any.whl`
- Asset size: 1,801,245 bytes
- Asset SHA-256:
  `d0b36bbeed783c791729ec263e6c6d222f1edf405d5c7b2789477a4e6f109245`

The GitHub asset digest, locally verified merged-build digest, and later public
download digest were identical.

## Merged wheel and public-install evidence

The exact merged tree produced a wheel that passed a clean-environment
build/install check:

- distribution version `0.3.315`;
- 145 of 145 manifested resources verified, 577,815 bytes total;
- 189 files in the wheel;
- `archive`, `wom`, `archive-mcp`, and `wom-mcp` all executed successfully;
- both MCP aliases reported version `0.3.315`, protocol `2025-03-26`, and the
  same complete 121-tool inventory;
- canonical MCP inventory SHA-256
  `931dc2bd42037c41b3bb2bb05b04dec5b4b4c58ebf384b57deb6420ef2d8be98`;
- runtime Skill lifecycle, onboarding preview, onboarding write, and strict
  doctor checks passed.

The public Release asset was then downloaded without authenticated GitHub API
access into a new temporary environment. Its size and digest matched the
published evidence. Fresh installation reported `wom-kit 0.3.315`, `pip check`
reported no broken requirements, and all four entrypoints plus both complete
MCP inventories passed again.

## Disposable v0.3.314 to v0.3.315 update canary

A disposable project-shaped fixture used an actual v0.3.314 source mirror and
the public v0.3.315 wheel. It did not contain real archive data.

1. The update dry-run returned `ready_for_approval`, zero blockers, and a
   `ready` materialization preflight.
2. A separate approved invocation returned `updated_restart_required`, zero
   blockers, and wrote a v0.2 update receipt.
3. The resulting source-mirror HEAD and peeled `v0.3.315` tag both resolved to
   the merge commit.
4. The project and source-mirror pins both became `v0.3.315`.
5. Tracked worktree and index differences were empty after the update.
6. A new process reported runtime alignment `aligned`, reason
   `running_version_matches_project_source`, complete tracked-source and
   resource verification, tag-at-HEAD, reachability from `origin/main`, and no
   warnings.

This proves the ordinary public update route on a representative disposable
project. It does not claim that every existing client filesystem shape is now
known.

## Beta-feedback decision

It is now appropriate to ask beta testers for scoped real-use feedback on the
published v0.3.315 artifact. Start with a small canary group before inviting
every client at once. Ask each tester to report:

- the old and new `archive --version` values;
- update dry-run status, approval status, elapsed time, and whether an
  operation reference remained visible;
- fixed blocker codes and recovery state, without private paths or content;
- whether a collision could be inspected and preserved, followed by a fresh
  updater dry-run and separate approval;
- original and derived partitions for paired batch capture;
- whether a natural-language request through the Codex or Claude desktop host
  reached a safe terminal outcome without manual command repair;
- time to recover after an interrupted or apparently silent operation.

This feedback can demonstrate end-to-end host reliability and repeated user
value. It must not yet be presented as broad market fit, general semantic
understanding, or universal client compatibility.

## Local cleanup boundary

Six disposable verification directories remain under the operating-system
temporary root because the app rejected the recursive cleanup command. They
contain only owned clone, wheel, and virtual-environment fixtures; no protected
client archive data was copied into them. No deletion was claimed.
