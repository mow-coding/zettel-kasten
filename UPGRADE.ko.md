# 업그레이드 가이드

[English Upgrade Guide](UPGRADE.md)

이 문서는 `zettel-kasten` / `zet`의 공개 버전 사이를 어떻게 이동해야 하는지 설명합니다.

이 프로젝트는 단순한 코드 묶음이 아니라, archive 규칙, zettel metadata, object manifest, provenance record, 미래의 `ZET` sharing envelope까지 함께 관리하는 버전형 프로토콜입니다.

## 기본 규칙

```text
PATCH upgrade -> 문서, 검증, 호환 가능한 수정
MINOR upgrade -> 호환 가능한 기능 추가 또는 optional field 추가
MAJOR upgrade -> protocol/schema breaking change
```

실제 archive를 업그레이드하기 전에는:

1. 대상 버전의 release note를 읽습니다.
2. private archive repository와 object manifest를 백업합니다.
3. `archive doctor --strict`를 실행합니다.
4. migration command가 있다면 먼저 dry-run으로 실행합니다.
5. 생성된 receipt를 확인한 뒤에만 private archive 변경사항을 커밋합니다.

아카이브는 사용자의 기억입니다. 조용히 몰래 다시 쓰면 안 됩니다.

## 공개 버전

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.2.15` | current public pre-release | `ai-archive-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `ai-archive-kit/docs/releases/v0.2.2.md` |

## `v0.2.14`에서 `v0.2.15`로

WOM Safe HTML Profile dry-run validator 패치이며, 호환 가능한 변경입니다.

변경 사항:

- `archive check-safe-html --path <zet> --dry-run`이라는 읽기 전용 CLI 명령을 추가했습니다. v0.2 Markdown 호환 zet가 미래의 WOM Safe HTML Profile 마이그레이션과 호환 가능한지 미리 검사합니다.
- validator는 `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URL, 그리고 `onclick=` 같은 inline event handler attribute가 zet body 안에 있으면 차단합니다.
- validator는 `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, `source_reference_preview` 필드를 포함한 구조화된 JSON을 반환합니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML 변환기, profile allowlist, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다. 기존 Markdown 호환 zets는 그대로 유효합니다.

```bash
git fetch --tags
git checkout v0.2.15
```

## `v0.2.13`에서 `v0.2.14`로

WOM Safe HTML Profile을 위한 호환 가능한 문서/스펙 기준선 패치입니다.

변경 사항:

- `WOM`, `zet`, `ZET`의 차이를 문서화했습니다.
- `zet`는 zettel-kasten 안에서 민팅되는 단위 문서라고 명확히 했습니다.
- `ZET`는 메신저, SNS/feed, 협업툴로 확장될 수 있는 미래 통신 계층이라고 명확히 했습니다.
- WOM Safe HTML Profile을 장기 canonical/interchange/rendering target으로 기록했습니다.
- Markdown은 v0.2 authoring/import compatibility format으로 유지했습니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.14
```

## `v0.2.12`에서 `v0.2.13`으로

호환 가능한 WOM 명칭 기준선과 CLI alias 패치입니다.

변경 사항:

- `WOM`을 전체 umbrella name으로, `Widesider of Modernity`를 그 확장명으로 기록했습니다.
- zet를 민팅하는 선호 명령으로 `archive mint-zet`을 추가했습니다.
- 기존 `archive mint-zettel`은 compatibility alias로 유지했습니다.
- 범위가 정해진 portable unit을 만드는 선호 명령으로 `archive parcel`을 추가했습니다.
- 기존 `archive pack`은 compatibility alias로 유지했습니다.
- parcel/workpack을 들여오는 과정을 미리 검토하는 선호 명령으로 `archive admit --dry-run`을 추가했습니다.
- 기존 `archive import --dry-run`은 compatibility alias로 유지했습니다.

실제 private archive migration은 필요 없습니다.

기존 스크립트는 옛 이름을 계속 써도 됩니다. 다만 새 사용자-facing 문서는 `mint-zet`, `parcel`, `admit`을 우선 사용해야 합니다.

```bash
git fetch --tags
git checkout v0.2.13
```

## `v0.2.11`에서 `v0.2.12`로

호환 가능한 real delegate receipt write 패치입니다.

변경 사항:

- `archive delegate-zet --approve --reviewed-by <actor>` 추가,
- 실제 delegate 실행 시 `receipts/delegate/*.delegate.json` 생성,
- `archive doctor`가 applied delegate receipt 검증,
- real delegate capability receipt에 nonce 생성,
- claim/spent/revocation registry는 아직 구현하지 않음을 명시.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.12
```

## `v0.2.10`에서 `v0.2.11`로

호환 가능한 delegate capability 계약 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run`에 `--target-policy counterparty_bound|claimable_once` 추가,
- `claimable_once` delegate preview에서는 `--target-archive` 없이도 실행 가능,
- `delegation_capability`, `claim_binding`, `settlement_condition` preview field 추가,
- settlement는 아직 비금융 상태이며 `mode: "none"`으로만 기록,
- 실제 P2P, claim registry, spent registry, revocation, blockchain, payment는 아직 구현하지 않음.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.11
```

## `v0.2.9`에서 `v0.2.10`으로

이 버전은 호환 가능한 dry-run lifecycle 기능 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run` 추가,
- `archive attest-zet --dry-run` 추가,
- `archive anchor-zet --dry-run` 추가,
- delegate, attest, anchor를 위한 read-only MCP check 추가,
- delegate receipt, attestation receipt, anchor metadata schema 추가.

private archive migration은 필요하지 않습니다.

실제 P2P, feed, transport, 외부 전송, foreign zet import는 아직 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.10
```

## `v0.2.8`에서 `v0.2.9`로

호환 가능한 용어 안정화 패치입니다.

변경 사항:

- 새 archive는 `human_minting`을 기본값으로 사용합니다.
- 기존 `human_promotion` archive도 계속 유효합니다.
- zettel rules에서 `minting_rules`를 사용할 수 있습니다.
- `promotion_rules`는 v0.2 legacy fallback으로 유지됩니다.
- 사용자-facing 문서는 minting 언어를 우선 사용합니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.9
```

## `v0.2.7`에서 `v0.2.8`로

호환 가능한 민팅 라이프사이클 기능 패치입니다.

변경 사항:

- `archive mint-zettel --dry-run`을 추가했습니다.
- `archive mint-zettel --approve --reviewed-by <id>`를 추가했습니다.
- `receipts/mint/` 아래 mint receipt를 추가했습니다.
- `receipts/mint/drafts/` 아래 draft snapshot을 추가했습니다.
- canonical zettel의 `mint` frontmatter를 추가했습니다.
- doctor가 mint receipt와 SHA-256 파일 연결을 검증합니다.
- read-only MCP `mint_zettel_check`를 추가했습니다.

실제 private archive migration은 필요 없습니다.

새 zettel을 민팅했다면 canonical zettel, mint receipt, draft snapshot을 함께 보관하세요.

```bash
git fetch --tags
git checkout v0.2.8
```

## `v0.2.3`에서 `v0.2.4`로

문서 정돈 패치입니다.

변경 사항:

- `README.md`를 더 정돈된 영문 프로젝트 진입 문서로 다시 작성했습니다.
- `README.ko.md`를 한국어 공식 진입 문서로 추가했습니다.
- 업그레이드 문서를 영문/한국어로 분리했습니다.
- 공개 포지셔닝, 현재 상태, privacy boundary, storage model, text provenance 설명을 정리했습니다.

실제 private archive migration은 필요 없습니다.

권장 명령:

```bash
git fetch --tags
git checkout v0.2.4
```

## `v0.2.2`에서 `v0.2.3`으로

한영 문서 병기 패치입니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.3
```

## `v0.2.1`에서 `v0.2.2`로

문서, provenance, 공개 히스토리 정리 패치입니다.

실제 private archive migration은 필요 없습니다.

중요 개념:

```text
original editable text != OCR/AI-derived text
```

둘 다 보관하지만, OCR/AI-derived text는 derivation metadata와 review status를 남겨야 합니다.

## 이전 버전에 남기

사용자는 오래된 버전에 남을 수 있습니다.

이것도 설계의 일부입니다.

```text
old version -> old rule set
new version -> updated rule set
```

미래의 sharing/collaboration 기능은 sender/receiver version을 명시해야 합니다.

## 앞으로의 릴리스 요구사항

앞으로 공개 릴리스는 반드시 다음을 포함해야 합니다.

- changelog entry,
- `ai-archive-kit/docs/releases/` 아래 release note,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
