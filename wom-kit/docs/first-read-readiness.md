# First-Read Readiness

`archive first-read-readiness` is a read-only gate between archive health and
AI memory reconstruction.

An archive can be structurally valid while some canonical zets still lack the
compact frontmatter abstract that a newly entering AI should read first. This
command reports that difference before the operator creates or consumes a full
private catalog.

```text
archive first-read-readiness <archive-root> --dry-run --progress --format json
```

Aliases:

```text
archive zet-first-readiness ...
archive memory-readiness ...
```

## What It Checks

The command enumerates every canonical zet path and reads frontmatter only. It
separately reports:

- an explicit `abstract`,
- a compatibility first read from `gist`, `summary`, `description`, or
  `overview`,
- a missing first read,
- unreadable frontmatter,
- policy-redacted entries, and
- missing, unsafe, or duplicate ids that prevent reliable follow-up reads.

`state: ready` requires every non-redacted canonical zet to have an explicit
`abstract` and every selected entry to have one uniquely resolvable safe id.
A compatibility field can make compact text available, but it does not satisfy
the explicit-abstract readiness gate.

The top-level `ok` is therefore a gate result. A successful scan with gaps
returns `ok: false` and `state: needs_attention` or `compatibility_only`; this
is evidence that the command worked and stopped an overclaim.

## What It Does Not Prove

The command does not read zet bodies, evaluate abstract meaning or quality,
prove that a host model consumed the abstracts, inspect objet bytes, call a
provider, check backup freshness, access a credential store, or write files.

The bounded attention list contains archive-relative paths, safe zet ids, and
status labels only. It never returns title, abstract, or body text; duplicate
id values are counted but not echoed.

## Recommended Order

1. Run `ai-start-here` and read archive-local instructions.
2. Run `first-read-readiness`.
3. If it is not ready, prepare reviewed repairs; never invent or auto-write
   missing abstracts.
4. When it is ready, run `zet-catalog-pass` to create one complete private
   first-read artifact.
5. Validate and consume that artifact from page zero, then delete it through
   the SHA-bound cleanup flow.

`first-read-readiness` proves current frontmatter readiness at one snapshot.
`zet-catalog-pass` is the separate evidence that a complete catalog artifact
was generated. The host still has to read the validated pages before claiming
that the AI consumed every first read.
