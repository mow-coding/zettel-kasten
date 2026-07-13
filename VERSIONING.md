# Versioning And Compatibility

`zettel-kasten`, `zet`, and `ZET` are designed as a versioned protocol family, not just a loose collection of scripts.

This matters because two people can only share, verify, and interpret zets safely when they understand which version of the system they are using.

## 1. Compatibility Principle

The practical rule is:

```text
same major protocol version -> expected to understand the same core archive and zet rules
different major protocol version -> migration or compatibility bridge may be required
```

In plain language:

```text
If two users are on the same major version, they should be able to recognize each other's zets.
If they are on different major versions, they may still keep using their older chain, but new features may not interoperate.
```

## 2. Release Tags Are Checkpoints

Not every commit is a stable compatibility point.

Stable public checkpoints should be Git tags:

```text
v0.1.0
v0.2.0
v1.0.0
```

These tags are the points that users, forks, and future `zet` clients should treat as named versions of the system.

## 3. Blockchain Analogy, Without The Hype

The project uses a loose blockchain-like mental model:

```text
source code + specs + schemas + release tags
```

define the shared rule set.

Users may choose to follow the latest release, or stay on an older release. Staying on an older release should remain possible, but it may limit compatibility with newer clients or sharing flows.

This repository is the public reference chain for the protocol and reference implementation.

## 4. What Gets Versioned

Versioned public artifacts include:

- `zet` document rules,
- metadata envelopes,
- JSON schemas,
- source/object manifest rules,
- minting receipts,
- sharing package rules,
- CLI behavior,
- MCP/server behavior,
- setup and onboarding behavior.

Private user data is not part of the public version chain.

## 5. Version Numbers

Use semantic versioning for public releases:

```text
MAJOR.MINOR.PATCH
```

Meaning:

- `MAJOR`: breaking protocol or schema changes.
- `MINOR`: compatible new features or new optional fields.
- `PATCH`: bug fixes, documentation fixes, or compatible validation fixes.

Before `v1.0.0`, breaking changes may still happen more often. They should still be documented clearly.

## 6. Migration Rule

When a future version changes the archive format, the project should provide:

- a migration note,
- a compatibility note,
- a dry-run migration command when practical,
- a receipt of what changed.

The archive should never silently rewrite a user's memory.

For the current v0.3 frontmatter contract, the schema stays unchanged, but older
v0.2-draft authoring guidance may have produced zettels without required nested
`provenance` and `visibility` subfields. Use:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before approving any frontmatter rewrite.

## 7. Current Version

Current public baseline:

```text
v0.3.230 pre-release
```

This baseline is for early review and prototyping. It is not yet a stable `v1.0.0` protocol.

## 8. Current Internal Package Version

The current `wom-kit` package metadata is:

```text
0.3.230
```

Therefore the current public compatibility tag for this repository should be:

```text
v0.3.230
```
