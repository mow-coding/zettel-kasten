# Decision Log - v0.3.185 adopt nonmatching resume diagnostics

Date: 2026-07-06

## Decision

Add diagnostics for same-provider object-storage locations that are digest-bound
but do not match the current adopt run's `store_ref` or resolved `remote_key`.
Also split doctor mint-link progress and make version import-origin drift more
visible.

## Context

Basoon's v0.3.183 revalidation confirmed that the matching resume summary works:
the current run had matching `wom_uploaded` rows and no matching
`declared_uploaded` rows. However, the archive also contained legacy declared
locations under another store reference. Operators needed to understand why
those rows did not increase the resume-skip count.

The same revalidation narrowed the doctor pause from target frontmatter loading
to `checking target mint receipt link`. That step was still too broad to tell
whether the pause was in field lookup, path formatting, comparison, or error
recording.

The run also exposed a local execution footgun: a project-local source mirror
can be pinned to one release while the active `archive` command imports a
different editable/global checkout.

## Consequences

- Matching provider/store/key rows and same-provider nonmatching rows are now
  counted separately.
- Nonmatching declared rows remain non-gating and never become skip proof.
- Doctor progress can identify the mint-link sub-step more precisely.
- `archive version` remains path-redacted by default but points operators to
  `--no-redact-local-paths` for local diagnosis.
- No archive migration or automatic store-ref normalization is introduced.
