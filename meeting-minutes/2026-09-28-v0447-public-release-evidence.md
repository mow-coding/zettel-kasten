# v0.4.47 public release evidence

WOM now supports unfinished activity recovery with Windows stream preservation,
scoped large Git backup, official external intake, consistent search pages and
unrelated archive work during another session's transfer. Disposable temporary
files are classified before intake/upload; uncertain material remains retained.
The product changes are described in [release notes](../wom-kit/docs/releases/v0.4.47.md).

## Exact source and checks

- [Product PR #154](https://github.com/mow-coding/zettel-kasten/pull/154): candidate `a53240d9d7b9c61de4fd229ef9f1bfad2e47c472`.
- [Full product CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36323680358), attempt 1: all required jobs including Required CI passed. Delivery-tools and focused-only lanes were intentionally skipped; they are not counted as executed tests.
- Squash merge / annotated `v0.4.47` target: `d3805946087444d74c742ac11d636c75c54f7dd9`.
- Candidate and merge complete tree: `4586b1fa8c6446cc00b761a051823a9e7e93a8db`.
- Annotated tag object: `1d2b62ab830f9489ce062e119cb690f36f2d776f`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36329256495) passed.

Earlier candidate runs failed or were superseded and cancelled. They are not
reclassified as passes. Corrections addressed intake cancellation/error contracts,
search and audit compatibility, bounded Git staging and authenticated partial
staging recovery. Test expectations were aligned with the requested concurrent
writer and historical-search behavior while retaining approval, privacy and
interruption assertions.

[Focused Windows verification](https://github.com/mow-coding/zettel-kasten/actions/runs/36323628534)
passed five synthetic tests, including 11,132 selected Unicode-path files, one
actual push, preservation of two other activity changes, interruption after an
add batch, unapproved index-byte rejection and resumption of the original claim.
The full-scale fixture recorded 208.547 seconds for execution on that runner;
this is not a customer-PC duration guarantee. Git add uses bounded 1,024-path /
256-KiB batches instead of extending the per-process timeout. Partial recovery
accepts only approved pre-add/post-add index bytes; two-path renames retain the
previous fully-staged recovery contract.

Separate installed synthetic journeys verified cleanup recovery without
reprocessing completed items, body/ADS preservation and restoration, and B's
search/intake/capture/zet link completing while A remained blocked in remote PUT.
Historical search pagination covered 311 mixed results during an index update.
These results establish development verification, not customer acceptance.

## Stable artifact and public installations

[Stable v0.4.47](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.47)
was published at **2026-09-27T15:42:37Z** and marked Latest.

- File: `wom_kit-0.4.47-py3-none-any.whl`
- Size: **3,499,655 bytes**
- SHA-256: `97835e4381d8aa814cf474fc5451975bd81408db3eb7ecd3cc1faf2298fac48a`

The attempt-1 CI installed-wheel artifact was retained and reused without
rebuilding. `verify_release_artifact.py` confirmed PR/CI/merge/tag/tree and exact
bytes with `same_full_tree_and_same_verified_wheel_bytes`. The draft asset was
downloaded and compared byte for byte before publication.

After publication, anonymous download matched the same size/hash. Two separate
fresh Windows environments installed from the downloaded file and public URL.
Both new processes returned `archive 0.4.47`, passed `pip check`, retained the
expected PEP 610 hash and verified all **180** package resources with zero
mismatches. See the [sanitized machine result](2026-09-28-v0447-public-install.md).

## Automatic beta

[Automatic delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36329326074)
completed before stable publication. Its source proof matched PR #154, the full
CI attempt and complete merge tree. Generated commit
`b76ffc2378a15cfc8c1701ea2a62fc8e120f3202` produced opt-in `v0.4.48b22`:
3,497,900 bytes, SHA-256 `7765560e011fdb138633420d9d787020ea457de284be7c6d238d64d5f0c6095f`.
Generated-wheel installation, anonymous public download and fresh public install
passed. This beta does not replace the stable Latest channel.

## Boundaries and follow-through

Customer archives were not used as development fixtures or modified by the
release work. Separate customer reply files identify the relevant improvements
and update checks; actual customer update and acceptance remain unverified.
Existing remote temporary objects are not automatically deleted. Cleanup outside
Windows remains planning/classification only. Working evidence and temporary
workspace cleanup are tracked separately from publication.
