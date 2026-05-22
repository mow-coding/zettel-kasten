# View Spec v0.1

A view is an AI-facing saved filter and context policy.

It is not a folder and not primarily a visual UI. It tells an AI which zettels, relations, and object metadata to retrieve for a task.

## Required Fields

```yaml
id: view.example.education
name: Example Education View
for: ai_context
filters: {}
include: {}
sort: []
context_policy: {}
```

## Example

```yaml
id: view.education.uos.extracurricular
name: Seoul Example University extracurricular
for: ai_context
filters:
  facets.domain: education
  facets.institution: Seoul Example University
  facets.activity_group: extracurricular
include:
  zettels: true
  originals: references_only
  relations: true
sort:
  - field: facets.school_year
    direction: ascending
  - field: created_at
    direction: ascending
context_policy:
  max_zettels: 50
  include_large_media: never_directly
  prefer_summaries: true
```

## Filter Semantics

The v0.1 filter language is intentionally simple:

```text
exact equality for scalar fields
contains for list fields
references_only for object files unless explicitly requested
```

Future implementations may compile this YAML into SQLite queries, search queries, or MCP tool calls.

