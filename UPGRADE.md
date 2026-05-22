# Upgrade Guide

This guide explains how to move between public `zettel-kasten` / `zet` versions.

The project is intentionally versioned because archive rules, zettel metadata, object manifests, and future `zet` sharing envelopes must be understandable across users and tools.

## 한국어 안내

이 문서는 `zettel-kasten` / `zet`의 버전별 업그레이드 방법을 설명합니다.

이 프로젝트는 단순한 코드 묶음이 아니라, archive 규칙과 `zet` 형식을 함께 관리하는 버전형 프로토콜입니다.

업그레이드 전에 항상 다음을 확인하세요.

1. 해당 버전의 release note를 읽습니다.
2. 실제 private archive를 백업합니다.
3. `archive doctor --strict`를 실행합니다.
4. migration이 있다면 먼저 dry-run으로 실행합니다.
5. 생성된 receipt를 확인한 뒤에만 실제 archive 변경사항을 커밋합니다.

아카이브는 사용자의 기억이므로 조용히 몰래 다시 쓰면 안 됩니다.

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
| `v0.2.3` | current public pre-release | `ai-archive-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.2.md` |
| `v0.2.1` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.1.md` |
| `v0.2.0` | first public pre-release baseline | `ai-archive-kit/docs/releases/v0.2.0.md` |

## From `v0.2.2` To `v0.2.3`

This is a bilingual documentation patch.

No private archive migration is required.

Recommended steps:

```bash
git fetch --tags
git checkout v0.2.3
```

한국어:

`v0.2.3`은 README와 업그레이드 안내에 한국어 설명을 병기한 문서 패치입니다. 실제 private archive migration은 필요 없습니다.

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
