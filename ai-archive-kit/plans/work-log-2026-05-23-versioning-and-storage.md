# Work Log: Versioning And Source Object Storage

Date: 2026-05-23

## 1. Purpose

Improve the public repository so readers understand:

- how `zettel-kasten` and `zet` should be managed by version,
- how compatibility should work across releases,
- who created the project,
- where ordinary document files belong in the storage model.

## 2. Versioning Work

Created:

```text
VERSIONING.md
CHANGELOG.md
UPGRADE.md
ai-archive-kit/docs/releases/README.md
ai-archive-kit/docs/releases/v0.2.0.md
ai-archive-kit/docs/releases/v0.2.1.md
```

The document explains:

- release tags are compatibility checkpoints,
- not every commit is a stable protocol version,
- same major version means expected compatibility,
- different major versions may need migration or bridges,
- migrations should be explicit and receipt-backed.

The first public compatibility tag should be:

```text
v0.2.0
```

because `ai-archive-kit` already uses package version `0.2.0`.

Follow-up:

After reviewing the public repository as a reader-facing project, a patch version was prepared:

```text
v0.2.1
```

Purpose:

- add explicit upgrade instructions,
- add per-version release notes,
- scrub local/private-looking example context,
- demonstrate the version maintenance pattern expected for future releases.

## 3. Authorship Work

Created:

```text
AUTHORS.md
CITATION.cff
```

Updated:

```text
README.md
NOTICE.md
LICENSE
CONTRIBUTING.md
SECURITY.md
ai-archive-kit/docs/github-repository-strategy.md
```

Public author identity:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
Undergraduate student, currently on leave
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

## 4. Source Object Storage Work

Created:

```text
ai-archive-kit/docs/source-object-storage-policy.md
```

Updated:

```text
ai-archive-kit/specs/object-manifest.md
README.md
```

The storage policy clarifies:

```text
minted zet -> Git zettel layer
original document -> object layer
object identity -> object manifest
extracted text -> search index or derived metadata
human conclusion -> minted zet
```

Document files such as `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, `.csv`, and `.pptx` are source objects when they are imported or cited as original files.

## 5. Public Tone

The user provided personal author details and also made a casual boastful remark. The public repo should preserve author identity and ambition without quoting the boastful line directly.

## 6. Public Hygiene Work

Scrubbed tracked public files for:

- actual local user path fragments,
- private-looking internal draft filenames in `.gitignore`,
- example identifiers that used the author's surname outside author metadata.

Public examples now use neutral values such as:

```text
C:\Users\example\dev\zettel-kasten
family:example-household
archive:child:example-child
```
