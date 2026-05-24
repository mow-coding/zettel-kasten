# Archive Spec v0.1

An archive is a sovereign memory space mounted by an AI runtime through a keyring profile.

Examples:

```text
personal archive
company archive
family archive
project archive
child archive
business unit archive
handover archive
```

## Required `archive.yml` Fields

```yaml
archive_id: archive:personal:example
name: Example Personal Archive
type: personal
principal:
  principal_id: person:example
  display_name: Example Person
  kind: person
root_policy:
  canonical_zettels: zettels/
  ai_inbox: inbox/
  views: views/
  object_manifest: objects/manifests/files.jsonl
  sqlite_schema: db/schema.sql
ai_write_policy:
  default: inbox_only
  canonical_requires: human_minting
storage_policy:
  object_identity: sha256
  provider_urls_in_zettels: forbidden
  locations_live_in_manifest: true
mounted_archives: []
```

## Archive Types

```text
personal
company
family
child
project
business_unit
relationship
handover
workpack
```

## Identity Document

Each archive also has:

```text
archive-identity.yml
```

It records:

```text
archive identity
principal identity
owner identity
operator identities
public key fingerprints
trusted counterparties
lineage hints
```

See:

```text
specs/archive-identity.md
specs/archive-lineage.md
```

## Mounting Rule

An AI runtime may only read or write archives explicitly mounted by the active keyring.

```yaml
mounted_archives:
  - archive_id: archive:personal:example
    access: read_write
  - archive_id: archive:family:example
    access: read_only
```

## Core Invariant

Archives do not casually merge. They share, derive, transfer, inherit, or federate with explicit provenance.
