# AI Start-Here Quick And Full Inspection

Status: quick/default and explicit full-Doctor contract implemented in v0.3.222;
safe full-Doctor receipt phase and callback coalescing added in v0.3.223

## Purpose

An AI entering a WOM archive needs a fast orientation map before broad reading.
That first map must not silently become a multi-minute complete archive scan.

## Quick Default

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
```

Quick mode reads bounded archive identity, policy, local-sovereignty authority,
canonical entrypoint presence, WOM-kit version context, and the current
operational-context record. It returns:

```text
inspection.mode: quick
inspection.full_doctor_run: false
inspection.doctor_summary.checked: false
```

It does not construct Doctor, enumerate every zet or receipt, read zet bodies,
read objet bytes, access a credential store/provider, or write archive state.
Its result is an entry map, not an archive health claim.

## Explicit Full Doctor

```powershell
archive ai-start-here <archive-root> `
  --dry-run `
  --full-doctor `
  --progress `
  --format json
```

Full mode runs the complete Doctor before composing the same start map. The
result changes to `inspection.mode: full_doctor`, embeds the Doctor severity
counts, and records observed reads under `inspection.read_observations`. Its
safety block can report:

- zet bodies read;
- local objet bytes read by validation;
- archive text scanned for secret-like patterns;
- no credential store accessed;
- no provider called;
- no archive state written.

Booleans describe this execution rather than marking every allowed read true.
This mode can take minutes on a large archive. That is expected complete
validation work, not the default cost of entering the archive.

## Progress Meaning

Counted progress identifies a stable unit. In particular:

```text
zettels -> zet_files
mint-receipts -> mint_receipts
```

Each counted line includes total elapsed time, stage elapsed time, rate, and
ETA. Heartbeats keep the latest count, so an operator can distinguish a long
single item from a process with no visible stage state.

Compact output prints the same stage/count at most once per 30 seconds unless
the event is a heartbeat. A receipt's many internal checks therefore cannot
produce dozens of identical `1/N progress` lines. Full detailed events remain
available through Doctor verbose/progress-log modes.

In v0.3.223, a long full-Doctor mint receipt heartbeat also names one fixed safe
phase such as `file_hash`, `target_edge_evolution`, or `edge_receipt_index`.
Private substep text never enters the phase. The shared reporter coalesces later
same-count callbacks before formatter/lock work while continuing to update the
phase used by heartbeat.

## Output And Privacy

`--output` remains an explicit private-scratch exception under
`.wom-scratch/diagnostics/`. It never turns the result into a receipt or public
artifact, refuses overwrite/traversal, and prints only a compact stdout summary.

Both modes redact local absolute paths by default. Progress never emits zet
ids, paths, titles, abstracts, bodies, receipt paths, provider values,
credential refs, tokens, or secret values.

## Compatibility

No archive migration is required. Scripts that relied on `ai-start-here` to run
a complete Doctor must add `--full-doctor`. Scripts that only needed the entry
map become faster without changing archive data.
