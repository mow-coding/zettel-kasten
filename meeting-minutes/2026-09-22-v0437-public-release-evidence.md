# v0.4.37 public release and development delivery evidence

Product scope: storage operations default to provable captures from the current session. Explicit delegation can select another session, exact objects, or all sessions. Partial-upload abandonment preserves existing effects. Full-access approval behavior is unchanged. This does not resolve every feedback item or prove customer acceptance.

## Product and source

- Product PR: #133, candidate `4570f781b90f9ace41ec9262206e82859e5666b5`.
- Merge/tag target: `e91a08ed4bdb4345abd05e41caf57ab99eeb0e8a`.
- Candidate/merge tree: `c6a414234b3135d739c549dc90b732d730748e02`.
- Annotated v0.4.37 tag object: `78dca6301b1253c7cacf2bebc481af69b9489eb9`.
- Incremental CI [35613497668](https://github.com/mow-coding/zettel-kasten/actions/runs/35613497668): success in 3 minutes 24 seconds; three focused platforms and Required CI passed. Baseline 35599830581 retains its failure result; all its failures map to the changed assertion and the new focused checks passed. Unchanged product/install/scale inputs and passed jobs are reused.
- Main CI 35613993992: short post-merge lane success.

## Stable artifact

[Public v0.4.37](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.37) was published at 2026-09-21T15:14:55Z. The exact installed-wheel artifact from baseline 35599830581 attempt 1 was retained; no second build replaced it. Fresh source, merge, tag, incremental-plan, job and byte comparisons passed before publication.

- File: `wom_kit-0.4.37-py3-none-any.whl`
- Size: 3345485 bytes
- SHA-256: `e664528fa46f57ad6672537248c0afea8d9aa1f88e2453f6b4d004a5087ec5b2`
- Draft asset downloaded and compared before publication; public API digest and size match.
- Public verification [35618240357](https://github.com/mow-coding/zettel-kasten/actions/runs/35618240357) passed: anonymous download; local-file and public-URL fresh Windows installations; archive 0.4.37; pip check; PEP610 hash; 174 resources / 748613 bytes / zero mismatches; exact public bootstrap recognition. Earlier attempts encountered HTTP504 and remain failures; the bounded transient-download retry preserved all checks.

## Beta and publisher correction

Automatic beta run 35614130037 passed generated-wheel installation checks, then failed when its newly created draft was queried through the public by-tag endpoint. The failure remains recorded. A corrected publisher resumed from the same checked bytes and published v0.4.38b1; it did not rebuild or overwrite assets.

- Beta source `ab9ceee42b684a6108c116da26c39972d61ac865`, tree `3afefff70fe882c7ce5d6902d1e9949d41495ca1`.
- Beta wheel size 3344207 bytes, SHA `6dc1c82a96d6aff90539ffa127524100d4bb147b6607becb0dcf616d63d23b3a`.
- Independent Windows [35617220991](https://github.com/mow-coding/zettel-kasten/actions/runs/35617220991) passed anonymous download, fresh public-URL installation, version and PEP610 hash checks. Local pip HTTP504 attempts remain failures and are not counted as passing.
- Publisher/source-binding repair PR #134: candidate `6ac97de052218df39012c3edad42998bc861d638`, CI35617574610 success, merge `bc8be9a52800bf7bd6625142ecdae0b25321c722`; candidate/merge tree `1ca80f9c6b86d3791ae564532076ec16c42ae471` matched.
- Repair used a delivery-tool-only lane with unchanged product verification contracts, Linux/Windows tool checks and readiness gates. It did not rerun the full product suite. Subsequent fully automatic beta publication is checked separately.

## Boundaries

All product validation uses synthetic inputs. No customer workspace was read or changed for these tests. Replies are delivered as files to the operator, not sent directly. Public installation verification and customer acceptance are distinct; customer acceptance remains unverified.
