# Decision Log - v0.3.183 Adopt Resume Gap and Doctor Frontmatter Progress

Date: 2026-07-06
Batch: v0.3.183.
Anchor: v0.3.182 public release.

## Problem

The basoon v0.3.182 revalidation confirmed that `--skip-existing-wom-uploaded` works, but the
archive had a different partial state than expected:

- many rows had matching Cloudflare/R2 provider-store-key locations;
- only a much smaller subset were verified `wom_uploaded` rows;
- `--skip-existing-wom-uploaded` correctly skipped only the `wom_uploaded` subset, then entered the
  remote HEAD loop for the rest.

The same revalidation showed that `doctor mint-receipts` progress improved, but the last visible
message was still too coarse: `loading target frontmatter`.

## Decisions

- **DEC-1 - Keep `declared_uploaded` non-gating.** A declared provider location is not a WOM
  provider confirmation and must not become a HEAD skip.
- **DEC-2 - Diagnose the gap instead of weakening the contract.** Adopt planning now counts
  matching provider/store/key locations by availability and warns when `declared_uploaded` rows
  explain the gap.
- **DEC-3 - Emit expected skip count before live HEADs.** Progress now prints a content-free resume
  summary after plan resolution and before `adopt-verify`.
- **DEC-4 - Keep output content-free.** Counts only; no object ids, remote keys, bucket names,
  provider URLs, credential refs, tokens, local paths, or secret values.
- **DEC-5 - Split target-frontmatter progress.** Doctor now emits internal read/BOM/fence/YAML/load
  and mint-link sub-steps around target frontmatter loading.

## Consequences

For basoon, the next adopt retry should first inspect:

```text
adopt-plan: resume summary matching_locations=... wom_uploaded=... declared_uploaded=... other=... skip_existing_wom_uploaded=on
```

If `declared_uploaded` is high and `wom_uploaded` is low, the run is not stuck: it is verifying and
promoting previously declared rows. If that is still too slow, the next design discussion should be
about a separate verified-adopt batching/rate strategy, not treating declared rows as verified.

For doctor, the next revalidation should report which target-frontmatter sub-step is the final
visible line if the first mint receipt is still slow.
