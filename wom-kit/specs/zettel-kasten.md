# Zettel-Kasten Layer Spec v0.2 Draft

The zettel-kasten layer is the controlled model that tells an AI runtime what kinds of things exist in an archive, which relationships are allowed, which actions may change state, and which policies must be checked before writing.

It does not replace zettels. The zettel remains the durable human-readable memory unit. The zettel-kasten layer makes the zettel-centered archive safer and more operational.

## Design Position

This project is inspired by the public architectural idea behind enterprise object/action modeling systems:

```text
objects + links + actions + logic + security
```

The WOM-kit translation is:

```text
zettels + original objects + typed edges + controlled actions + policies + keyrings
```

The goal is not to clone Palantir Foundry. The goal is to make a PC-first, AI-native archive where an AI acts inside a governed model instead of freely mutating a pile of files.

## Relationship To v0.1 Layers

v0.1 defined the file protocol:

```text
archive.yml
zettels/
inbox/
views/
objects/manifests/files.jsonl
db/schema.sql
workpacks/
```

v0.2 adds the zettel-kasten layer:

```text
zettel-kasten/
  types.yml
  actions.yml
  policies.yml
  zettel-rules.yml
```

This layer is a draft contract. It is not yet enforced by a CLI, MCP server, or runtime.

## Core Files

### `zettel-kasten/types.yml`

Defines entity types, value types, and link types.

Examples:

```text
Archive
Principal
Zettel
OriginalObject
View
Workpack
Receipt
```

This file answers:

```text
What kinds of things can the archive talk about?
Which fields identify them?
Which relationships are allowed?
Where are they stored in files or SQLite?
```

### `zettel-kasten/actions.yml`

Defines controlled actions.

Examples:

```text
create_draft_zettel
promote_zettel
attach_object
derive_zettel
pack_work_context
import_workpack
archive_doctor
archive_init
```

This file answers:

```text
What is the AI allowed to do?
What inputs are required?
Which files or records may be written?
Which policies must be checked?
What receipt or audit trail is required?
```

### `zettel-kasten/policies.yml`

Defines safety, authorization, and archive integrity policies.

Examples:

```text
AI writes to inbox by default.
Canonical zettels require human minting.
Provider URLs are forbidden inside zettels.
AI may only access mounted archives.
Workpack imports require receipts.
Substantial project work must be recorded.
```

This file answers:

```text
What must never happen?
What requires human approval?
What must be logged?
Which archive boundaries must be respected?
```

### `zettel-kasten/zettel-rules.yml`

Defines zettel lifecycle rules.

Examples:

```text
draft creation
promotion checklist
one-idea rule
record-note exception
revision history rule
AI behavior while drafting
```

This file answers:

```text
When is a zettel only a draft?
When can a draft become canonical?
When should a draft be split?
When should revision create history instead of overwriting?
```

## Type Model

The v0.2 draft uses three simple groups.

```text
value_types
  Reusable scalar concepts such as datetime, sha256_object_id, archive_id, path.

entity_types
  Nouns in the archive world, such as Zettel, OriginalObject, View, Workpack.

link_types
  Typed relationships, such as references, derived_from, shared_with, supersedes.
```

For beginners: think of an entity type as a table shape or object shape, and a link type as a named arrow between two things.

## Action Model

An action is not just a shell command. It is a governed change.

Each action definition should include:

```text
action_id
display_name
description
actor_types
inputs
policy_checks
preconditions
writes
outputs
receipt
```

The archive may later compile actions into CLI commands, MCP tools, scripts, or AI tool calls.

## Policy Model

Policies are intentionally declarative in v0.2.

They should be easy to read before they are clever to execute.

The policy file may later compile to a real policy engine, but v0.2 keeps a simple YAML format:

```text
policy_id
decision
applies_to
condition
enforcement
reason
```

Recommended decisions:

```text
allow
deny
require_human_approval
require_receipt
allow_with_constraints
```

## Runtime Boundaries

v0.2 does not implement:

```text
runtime policy enforcement
MCP server
CLI commands
JSON Schema validation
OPA/Rego policy execution
database migrations
Notion migration
```

Those come later. The purpose of v0.2 is to make the model explicit before writing tools around it.

## Design References

The zettel-kasten layer follows common ideas from:

- Palantir public object/action documentation: object types, link types, action types, and object permissioning.
- W3C PROV: provenance as a model for describing where records came from and how they changed.
- Open Policy Agent: policy as structured, evaluable rules.
- JSON Schema: later validation can split core structure from validation rules.

## Core Principle

```text
The AI may act, but only through named actions inside a typed and policy-governed archive.
```
