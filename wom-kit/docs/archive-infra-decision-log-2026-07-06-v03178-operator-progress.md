# Decision Log - v0.3.178 Operator Progress for Doctor and Adopt

Date: 2026-07-06
Batch: v0.3.178.
Anchor: v0.3.177 public release.

## Problem

The basoon v0.3.176 verification letter reported long silent runs for `doctor --strict` and a
large `object-storage-adopt-existing --key-map` batch. Silence is operationally unsafe: the
operator cannot distinguish a slow live HEAD loop from a hang.

## Decisions

- **DEC-1 - Expose existing Doctor progress.** `Doctor` already had stage callbacks; add
  `archive doctor --progress` and wire it to stderr. Rationale: minimal change, no diagnostic
  payload churn.
- **DEC-2 - Reuse the validate progress formatter.** Generalize the formatter to
  `make_stage_progress_callback(label=...)`; keep `make_validate_progress_callback` as a wrapper.
  Rationale: one output style for long validation-style commands.
- **DEC-3 - Add adopt service callback.** Add an optional callback to
  `object_storage_adopt_existing_run`, then emit events for plan resolution, declared adopt, and
  verified remote HEAD loops. Rationale: CLI and future callers can observe long batches without
  changing result JSON.
- **DEC-4 - Throttle item progress.** For large adopt loops, emit first / every 100th / final
  item. Rationale: a 19k-object run needs a heartbeat, not 19k lines per stage.
- **DEC-5 - Progress is content-free.** Events carry only stage, message, current, and total.
  Rationale: no object ids, remote keys, bucket names, provider URLs, exact credential refs,
  tokens, secrets, provider bodies, or local absolute paths.
- **DEC-6 - Default output unchanged.** No progress is emitted unless `--progress` is passed.
  Rationale: additive patch, no script compatibility break.

## Consequences

Operators can rerun:

```bash
archive doctor <archive-root> --strict --progress
archive object-storage-adopt-existing <archive-root> ... --approve --progress --format json
```

and see whether the command is advancing through stages. The JSON/text result remains the
ordinary command result; progress is stderr-only.

