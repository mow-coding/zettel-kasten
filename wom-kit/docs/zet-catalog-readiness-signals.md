# zet Catalog Readiness Signals

Status: implemented in v0.3.209

## Why Three Signals Exist

Finishing every catalog page proves that WOM visited every selected local zet
file. It does not prove that every zet had a readable abstract, and it does not
prove that every zet can later be resolved by a unique id.

The strict catalog therefore reports three separate signals:

| Signal | Plain meaning |
| --- | --- |
| `archive_wide_coverage_claim_ready` | Every selected zet file was returned through one strict, unskipped catalog chain. |
| `archive_wide_abstract_reading_claim_ready` | zet coverage is ready and every non-redacted zet supplied readable first-read text. |
| `archive_wide_followup_resolution_ready` | zet coverage is ready and every zet has a readable, safe, unique frontmatter id for id-only follow-up. |

Do not substitute one signal for another. In particular, a host must not say
“I read every abstract” when only zet coverage is true.

## Abstract Coverage

`abstract_coverage` reports:

- selected zet count;
- number of zets that require first-read text;
- readable first-read count;
- missing or unreadable first-read gap count;
- count intentionally redacted by policy;
- whether all required first reads are available.

An explicit `abstract` and a safe compatibility field (`gist`, `summary`,
`description`, or `overview`) both count as readable. A redacted zet remains in
zet coverage but is excluded from the abstract requirement because its content
is intentionally suppressed. Missing and unreadable frontmatter remain gaps.

## Identity Coverage

`identity_coverage` reports counts for safe readable frontmatter ids, duplicate
id values, entries affected by duplicate ids, and entries that cannot be
addressed safely by id. It does not echo archive-relative paths or duplicate id
values in the summary.

A duplicate-id zet file is still returned, so exhaustive zet coverage is not
silently narrowed. However, id-only follow-up is not ready because the host
cannot honestly say which file an ambiguous id selects.

## Safe Boundary

The readiness check is read-only. It does not:

- derive an abstract from a zet body;
- rewrite a missing or duplicate id;
- create a revision candidate;
- persist a reading loop or completion receipt;
- call an LLM, provider, or generated index.

Report gaps to the human and use the archive's reviewed repair workflow. Do not
turn absence into invented memory.

In v0.3.212 compact continuation responses, detailed `abstract_coverage` and
`identity_coverage` remain on the required full first page rather than being
repeated. Their three readiness booleans remain in `coverage` on every page.
The host must retain the first page if it needs to explain a final false signal.
