# Decision Log - v0.3.182 Adopt Resume and Doctor Progress

Date: 2026-07-06
Batch: v0.3.182.
Anchor: v0.3.181 public release.

## Problem

The basoon v0.3.180 revalidation showed that the v0.3.180 adopt-plan manifest index worked on the
real large archive, but the next bottlenecks were still operationally painful:

- `adopt-verify` remote HEADs were roughly 0.49 seconds per object across about 19k objects.
- An interrupted adopt left partial verified receipt/manifest writes, making resume behavior
  important.
- `doctor --strict --progress` still became opaque inside `mint-receipts`, especially after the
  first receipt progress line.

## Decisions

- **DEC-1 - Do not make manifest-skip the default.** Verified adopt still re-HEADs by default so
  the conservative freshness behavior is unchanged.
- **DEC-2 - Add an explicit resume helper.** `--skip-existing-wom-uploaded` skips remote HEAD only
  for rows that already have a matching `wom_uploaded` manifest location for the same
  provider/store/resolved key.
- **DEC-3 - Refuse conflicting stronger verification.** The resume helper is refused with
  `--content-hash-verify`; a fresh content-hash verification request must not be reduced to a
  manifest-only skip.
- **DEC-4 - Count and name partial-adopt resume state.** Adopt summaries now expose existing and
  skipped manifest counts, and the command emits a `resume_hint` when matching rows exist but the
  resume option is off.
- **DEC-5 - Add mint-receipts sub-step progress.** Doctor progress now reports sampled internal
  sub-steps and cache hit/miss summaries for the receipt stage without changing diagnostics.

## Consequences

For basoon's partial adopt state, the next intended retry shape is:

```bash
archive object-storage-adopt-existing <archive-root> ... \
  --key-map <map.jsonl> \
  --approve \
  --skip-existing-wom-uploaded \
  --progress \
  --format json
```

If most rows already have matching `wom_uploaded` manifest locations, the run should skip their
HEADs and spend live provider time only on the rows not yet adopted.

For doctor, the next revalidation should capture the last `mint-receipts` sub-step and cache
summary if the stage is still slow.
