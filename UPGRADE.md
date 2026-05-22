# Upgrade Guide

This guide explains how to move between public `zettel-kasten` / `zet` versions.

The project is intentionally versioned because archive rules, zettel metadata, object manifests, and future `zet` sharing envelopes must be understandable across users and tools.

## Quick Rule

```text
PATCH upgrade: documentation, validation, or compatible fixes
MINOR upgrade: compatible new features or optional fields
MAJOR upgrade: breaking protocol/schema changes
```

Before upgrading a real archive:

1. Read the target version note in `ai-archive-kit/docs/releases/`.
2. Back up the private archive repo and object manifests.
3. Run `archive doctor --strict`.
4. Run any migration command in dry-run mode first.
5. Commit private archive changes only after reviewing generated receipts.

The archive should never silently rewrite memory.

## Public Versions

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.2.2` | current public pre-release | `ai-archive-kit/docs/releases/v0.2.2.md` |
| `v0.2.1` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.1.md` |
| `v0.2.0` | first public pre-release baseline | `ai-archive-kit/docs/releases/v0.2.0.md` |

## From `v0.2.1` To `v0.2.2`

This is a documentation, provenance, and public-history hygiene patch.

No private archive migration is required.

Recommended steps:

```bash
git fetch --tags
git checkout v0.2.2
```

Important concept change:

```text
original editable text != OCR/AI-derived text
```

Both should be stored, but OCR/AI-derived text should keep derivation metadata and review status.

## From `v0.2.0` To `v0.2.1`

This is a documentation and public-repository hygiene patch.

No private archive migration is required.

Recommended steps for users:

```bash
git fetch --tags
git checkout v0.2.1
```

For contributors working on `main`:

```bash
git pull
cd ai-archive-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

## Staying On An Older Version

Users may stay on an older version.

That is part of the design:

```text
old version -> old rule set
new version -> updated rule set
```

Future sharing and collaboration features should make the sender/receiver version explicit.

## Future Release Requirements

Every future public release should include:

- changelog entry,
- release note under `ai-archive-kit/docs/releases/`,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy warning when relevant,
- Git tag,
- GitHub Release.
