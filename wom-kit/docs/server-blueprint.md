# Server Blueprint

The server is a coordination node, not the default source of truth.

The user's local archive remains primary unless a specific archive chooses otherwise.

## Server Roles

```text
personal server
  Backup and sync for one person's private archive.

family server
  Shared coordination for family records.

company server
  Backup, permission, and coordination for company and business-unit archives.

project server
  Temporary collaboration space around a project or workpack.
```

## What A Server Stores

In the v1 direction, a server may store:

```text
archive identity documents
signed or unsigned workpacks
receipts
view manifests
object metadata
encrypted object copies when explicitly allowed
```

The server should not assume it can read a user's entire private archive.

## Ownership Rule

The server must not assume the current writer is the archive owner.

```text
owner
  The person, family, company, or other group that owns the archive.

operator
  The person or role currently allowed to work on the archive.
```

A family server may coordinate a child archive while the family is the owner and parents are operators. Later, a receipt-backed ownership transfer can make the child the owner.

## Sharing Rule

Sharing should happen through a selected view or workpack:

```text
local archive
  -> scope gate dry-run
  -> trust gate dry-run
  -> human approval
  -> receipt
  -> optional server sync
```

## Future Server Trust

The server should have its own archive/server identity:

```yaml
identity_id: identity:server:example
scope: server
public_keys:
  - fingerprint: SHA256:...
```

Clients should verify server identity before pushing or pulling shared archive material.
