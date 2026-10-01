# v0.4.56 public release evidence

This WOM-kit release answers beta letter 179, sent from v0.4.54, which the customer had installed and updated to successfully. An existing R2 key file moves into the Windows Credential Manager under one approval or the session grant; the Git backup preview no longer stops on Windows directory-size noise (reproduced with no writer) and reports real drift by kind and category; offload is no longer blocked by valid session-evidence drafts and frees verified bytes that came back; after an update missing `.gitignore` rules are named; `activity-cleanup --status` reports completion boundaries; Doctor no longer reports a false cache-stale error on Windows. It does not establish the customer's own run.

## Source and checks

- [Product PR #170](https://github.com/mow-coding/zettel-kasten/pull/170): candidate `949dbc5f17c0b114102b39265ccede94fd9a7622`; [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36845293291) and Required CI passed. The previous head failed on Ubuntu only in two new drift-classification tests (Linux `st_ctime` is change time), fixed in the candidate.
- Squash merge and annotated `v0.4.56` target: `2e7910baa783db7dff69c47d6d65e7a6064b53c8` (tag object `2b9624533b88dc2b6dbd0cd8f1a56ee6f052e588`). Candidate and merge complete tree: `0a78b3ce6365f8ac90bb8b7820dbc0410144d721`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36856150154) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36856424687) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.56](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.56) became Latest at **2026-10-01T11:38:23Z**:

- `wom_kit-0.4.56-py3-none-any.whl`
- **3,648,262 bytes**
- SHA-256 `2f569b7ba4f2cc4dd35d25f65d69e268f0f22d5b3a7769590b5378eab5178c17`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-01-v0456-public-install.md).

## How the letter's conditions were reproduced

The Git preview drift: the real CLI on a synthetic archive with thousands of receipts on Windows and no writer, plus a monkeypatched flipping directory size. The session-evidence draft: a real reviewed_session_evidence draft created through the draft writer next to an eligible object. The reappeared bytes: an offloaded row with its file present, a capture `re_materialize` and a full re-offload run on Windows. The key file: dotenv, INI and JSON files through the isolated reader with a credential-store double. Doctor: the offload test that failed about five of six runs on a developer PC passed six of six with the fix. The design is in `wom-kit/docs/archive-infra-decision-log-2026-10-01-letter-179.md`.

## What this release does not prove

The customer's key file format, Windows build, which step recreated their 240 files and their own runs are not confirmed.
