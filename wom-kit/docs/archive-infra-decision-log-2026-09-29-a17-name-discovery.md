# Decision log: finding a registered objet by its original filename (A17, 2026-09-29)

## Context

Beta letter 176 registered 21 external originals through `source-intake-batch
--stage-external` and `objet-capture-batch`. Searching by the original filename
returned nothing, and `find-objet` had an empty alias authority. The owner
delegated the design on 2026-09-25; this is Claude's recommendation, recorded
as delegated and implemented in the same release.

## Facts

- The staged copy is content-addressed (`<ordinal>-<sha256>.bin`), so the
  original basename survived only in the private intake request. Nothing wrote it
  anywhere a lookup could read.
- Filenames are private metadata under the v0.3.295 contract. They are written by
  the v0.3.296 `objet-source-metadata-write` engine from one reviewed intake per
  object, into the private manifest, a private receipt and the private alias
  index that `find-objet` reads. That engine applies rows on Windows only.
- The objet id is the byte digest, so staging already knows the id the later
  capture will register.

## Decisions

1. **Staging prepares the name intakes.** When an external copy is approved,
   staging writes one derived private intake per copy under
   `.wom-scratch/private/objet-source-metadata/<execution>/`, with the original
   basename, the verified size, the declared media type when the request named one,
   the source-intake receipt digest as observation evidence and the approved
   staging plan digest as review evidence. The write is part of the already
   approved staging; it is idempotent on resume and fails closed on a different
   prepared file. The staging result reports `prepared_name_intake_count` and the
   follow-up command.
2. **One approval writes every prepared name.** `objet-source-metadata-write
   --intake-batch <execution>` plans every prepared intake with the ordinary
   per-row engine plan, binds them into one content-free batch digest and, after
   one exact approval (no dialog under a valid session grant), writes the rows one
   by one. Each row's engine digest is re-derived right before its write, because
   every append changes the private manifest. Already written names are skipped,
   so a second run only writes what remains.
3. **The single-row path is unchanged.** `--intake` keeps its contract; the two
   modes are mutually exclusive.
4. **Not done: writing the name row inside the capture claim.** The engine keys
   its approval to its own operation. Letting the capture claim carry a
   private-metadata write would change that contract for every caller, which is
   more than one release should carry.

## Boundaries

- The name write is Windows-only, like the single-row engine.
- Validation is synthetic: three named originals through staging, capture, one
  batch approval, `index` and `find-objet`; receipts, the object manifest and
  public results contain no filename. A customer's own run is not confirmed.
- The example archive's object manifest carries one blank line, which the strict
  private writer refuses; tests normalize their copy. Whether real archives carry
  blank lines is not known.
