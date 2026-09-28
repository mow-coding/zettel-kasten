# v0.4.48 public release evidence — scoped session backup

This release fixes a session Git backup being blocked by a large changed file from another activity. WOM selects the authenticated session paths before applying file-size, content and Git-attribute checks; the selected files retain the existing limits. Other activities' working and staged changes remain outside the selected backup. [Release scope](../wom-kit/docs/releases/v0.4.48.md).

## Exact source and checks

- [Product PR #156](https://github.com/mow-coding/zettel-kasten/pull/156): candidate `dfa05cbd7150280faf9bca432b233231390c2ff0`.
- [Full product CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36343219560), attempt 1: all required platform and installation jobs, including Required CI, passed. Earlier candidate runs failed or were superseded; they are not counted as passes.
- Squash merge and annotated `v0.4.48` target: `798ba5760507ad266e81c9360afb1776b36661b1`. Candidate and merge complete tree: `66f3822e548545a7185e1450bfa4bfd7ea864f11`. Annotated tag object: `99a1f36093a5b768c886ec977cc946a28dbaec34`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36385252304) and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36386565491) passed. Their skipped full product shards are not presented as executed tests.
- A separate local installed session-backup journey hit its 1,800-second limit; its partial observations are not counted as a pass. The exact candidate's full CI, focused scope and original-approval recovery tests, and installed-wheel gate passed.

## Automatic beta before stable publication

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36385351679) completed first. Its source proof names the exact PR, passed CI attempt, merge and complete tree above. It generated commit `008075a496ab98f893c2a51db6e1a5bd2c2539aa` and opt-in `v0.4.49b24`: 3,499,764 bytes, SHA-256 `c90ecd396c03ed69f2b1f504bef7747bf36db6f6a315eb615ce53f45419a76ee`. Generated-wheel installation, anonymous download and fresh public installation passed. The beta is separate from the stable Latest channel.

## Stable artifact and public installations

[Stable v0.4.48](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.48) was published at **2026-09-28T06:28:17Z** and marked Latest.

- File: `wom_kit-0.4.48-py3-none-any.whl`
- Size: **3,500,519 bytes**
- SHA-256: `25fb0b241ee8a82cc2f36c6bf583a84267e52882226ff9c9414a6f1e2f3f49cd`

The attempt-1 CI installed-wheel artifact was retained and reused without rebuilding. `verify_release_artifact.py` confirmed the PR/CI/merge/tag/tree and exact bytes with `same_full_tree_and_same_verified_wheel_bytes`. The draft asset was downloaded and compared byte for byte before publication. After publication, anonymous download matched the same size and SHA-256. Two separate fresh Windows environments installed from the downloaded file and the public URL. Both new processes returned `archive 0.4.48`, passed `pip check`, retained the expected PEP 610 hash and verified all 180 packaged resources without mismatches.

Customer archives were not used for development tests. Existing remote temporary-object deletion, provider intake and other historical requests remain open. An installed customer update and customer acceptance have not been verified.
