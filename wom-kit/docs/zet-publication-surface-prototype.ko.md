# ZET Publication Surface Prototype

상태: 공개 UX 인사이트
날짜: 2026-05-26

이 문서는 `ZET` 통신 계층의 미래 UI를 구상하기 위한 작은 프로토타입 사례를 정리한다.

사례의 출발점은 다음 흐름이다.

```text
데스크톱 AI 런타임에서 대화
-> AI가 대화를 요약하고 구조화
-> 사용자가 검토
-> 개인 아카이브용 글로 정리
-> WordPress.com 비공개 블로그에 게시
-> 모바일/웹에서 다시 읽고 검색
```

이 흐름은 WordPress 자체가 `ZET`라는 뜻이 아니다. WordPress는 여기서 이미 정리된 기록을 외부 전시 surface로 보여주는 임시 구현체다. 핵심 인사이트는 `zet`를 만든 뒤 그것을 어떻게 읽기 좋은 화면으로 project하고, 필요할 때 외부 surface에 발행할 수 있는가에 있다.

## 1. 왜 이 사례가 ZET UI에 유용한가

현재 WOM 모델은 다음 경계를 중요하게 본다.

```text
draft zet
-> human review
-> mint
-> private archive memory
-> optional later sharing/projection
```

WordPress 아카이브 사례는 이 경계를 실사용 화면으로 보여준다.

- AI가 대화를 바로 공개 게시하지 않는다.
- 먼저 사람이 읽을 수 있는 요약 글을 만든다.
- 제목, 본문 구조, 카테고리, 공개 범위를 사용자가 이해할 수 있게 정한다.
- 외부 게시물은 canonical archive memory가 아니라 읽기 좋은 projection이다.
- 게시 후에는 모바일 앱, 검색, 날짜별 목록 같은 familiar UI를 통해 다시 접근한다.

즉, 이 사례는 `mint -> delegate/share/export` 사이에 필요한 UX를 보여준다.

## 2. 제품 관점 번역

WordPress 사례를 WOM/ZET 언어로 번역하면 다음과 같다.

```text
AI conversation
  source/provenance candidate

archive summary
  draft zet candidate

human-reviewed archive post
  mint candidate or minted zet projection

WordPress post
  external publication surface

WordPress URL
  surface locator, not canonical identity

publish API response
  projection receipt candidate
```

중요한 점은 외부 URL이 `zet`의 본체가 아니라는 것이다. URL은 surface 위치다. canonical identity는 archive 안의 `zet` id, content hash, receipt, provenance가 담당해야 한다.

## 3. 사용자 흐름

권장 UX 흐름은 다음과 같다.

```text
1. 대화가 끝난다.
2. AI가 "아카이브 초안 만들기"를 제안한다.
3. 사용자는 초안을 읽고 제목과 범위를 확인한다.
4. 시스템은 private archive에 남길 record와 외부 projection을 분리해서 보여준다.
5. 사용자는 "아카이브에 남기기"와 "외부 surface에 게시"를 별도로 승인한다.
6. 게시 후 시스템은 canonical record와 projection receipt를 함께 보여준다.
```

화면 단위로 보면 다음이 필요하다.

```text
Conversation review panel
  오늘의 핵심, 결정, 다음 질문을 보여준다.

Zet draft preview
  archive에 남길 문서 본문과 metadata envelope를 보여준다.

Projection preview
  WordPress, feed, workspace, message 등 외부 surface에서 어떻게 보일지 보여준다.

Scope gate
  포함되는 내용과 빠지는 내용을 명확히 보여준다.

Publish confirmation
  외부 surface, visibility, title, slug, target category/channel을 확인한다.

Receipt view
  source conversation ref, minted zet ref, projection target, external post id, hash를 보여준다.
```

## 4. Custom UI에 필요한 핵심 컴포넌트

### Draft Summary Composer

AI가 만든 초안을 사용자가 빠르게 고칠 수 있는 화면이다.

필요한 필드:

- title
- 핵심 요약
- 결정된 것
- 다음에 이어갈 질문
- source/provenance note
- redaction checklist

이 화면은 글쓰기 앱처럼 보여야 한다. 사용자가 protocol packet을 편집한다고 느끼면 안 된다.

### Archive/Projection Split View

같은 기록을 두 겹으로 보여준다.

```text
왼쪽: private archive에 남는 canonical 또는 draft zet
오른쪽: 외부 surface에서 보일 projection preview
```

사용자가 이해해야 하는 말은 간단하다.

```text
내 archive에 남는 기록
밖에서 보이게 만드는 화면
```

### Scope Gate

게시 직전에 다음을 체크한다.

- private source가 포함되어 있는가
- 실제 대화 원문이 그대로 들어갔는가
- 로컬 파일 경로나 토큰이 들어갔는가
- 외부 surface가 private인지 public인지
- 댓글, 검색 노출, 링크 공유가 어떻게 동작하는지

ZET의 미래 공유 기능에서는 이 scope gate가 delegate capability 설정 화면으로 확장될 수 있다.

### Projection Receipt

게시가 끝나면 사용자는 단순히 "완료"만 보는 것이 아니라 어떤 일이 일어났는지 확인해야 한다.

```text
source: AI conversation/session reference
zet: minted or draft zet id
projection: wordpress_private_blog
external_id: provider post id
external_url: provider URL
content_hash: projected body hash
visibility: provider-level private site
reviewed_by: user/person id
published_at: timestamp
```

이 receipt는 나중에 `attest`, `anchor`, `delegate`와 연결될 수 있는 기초 evidence다.

## 5. WordPress 사례에서 얻은 UI 원칙

### 사용자는 블로그형 목록을 이해한다

날짜별 글 목록, 검색창, 제목, 썸네일은 익숙하다. ZET의 feed/workspace UI도 너무 protocol-first로 시작할 필요가 없다. 처음 화면은 사용자가 이미 이해하는 글 목록이어야 한다.

### private/public을 surface 단위로 설명해야 한다

사용자는 "이 글이 private인가?"를 묻는다. 하지만 실제로는 다음 두 층이 있다.

```text
archive visibility
surface visibility
```

WordPress 사례에서는 사이트 전체가 비공개라서 개별 글은 `publish` 상태로 둘 수 있었다. ZET UI도 이 차이를 숨기지 말고 부드럽게 설명해야 한다.

### posting은 minting이 아니다

게시 버튼이 archive memory를 확정하는 버튼이 되어서는 안 된다.

권장 버튼 분리:

```text
초안 저장
아카이브에 남기기
외부에 게시하기
```

나중에 제품 언어가 안정되면 다음처럼 매핑할 수 있다.

```text
아카이브에 남기기 ~= mint
공유 권한 만들기 ~= delegate
받은 기록 확인하기 ~= attest
내 맥락에 놓기 ~= anchor
```

### 외부 surface는 projection이어야 한다

WordPress post body는 사용자가 읽기 좋은 HTML이다. 하지만 이것이 canonical zet format을 대체하면 안 된다.

권장 내부 모델:

```text
canonical zet
  metadata envelope + text body + provenance + hash

projection
  surface-specific title/body/category/thumbnail/slug

projection receipt
  canonical zet와 외부 provider post를 연결하는 evidence
```

## 6. 최소 데이터 모델 후보

```yaml
projection_id: projection_20260526_example
source_zet_id: zet_20260526_example_ai_archive_summary
source_zet_hash: sha256:example
surface:
  kind: wordpress_private_blog
  provider: wordpress.com
  site_ref: provider_site:example_private_archive
target:
  status: publish
  category: example_owner
  external_post_id: "123"
  external_url: https://example.invalid/2026/05/26/example/
visibility:
  archive_scope: private
  surface_scope: private_site
review:
  reviewed_by: person:example_owner
  reviewed_at: 2026-05-26T16:00:00+09:00
integrity:
  projected_body_sha256: sha256:example
redactions:
  private_paths: excluded
  credentials: excluded
  raw_conversation: summarized
```

## 7. 구현 예시 위치

이 문서와 함께 다음 sanitized example을 둔다.

```text
wom-kit/examples/zet-publication-surface/
  README.ko.md
  zet-publication-envelope.example.json
  wordpress-post.safe-html.example.html
  wordpress-publish.example.ps1
```

이 예시는 실제 개인 WordPress 사이트, 토큰, local path, private conversation을 포함하지 않는다. 목적은 UI/UX와 data contract의 모양을 보여주는 것이다.

## 8. 다음 구현 후보

다음 작은 구현 단위는 provider API를 실제로 붙이는 것이 아니라, local archive 안에서 projection preview와 receipt preview를 만드는 것이다.

가능한 CLI preview:

```text
archive projection-plan <archive-root>
  --zet <zet-id-or-path>
  --surface wordpress_private_blog
  --dry-run
  --format json
```

가능한 출력:

```text
ok
blockers
warnings
projection_preview
scope_gate
receipt_preview
would_call_provider: false
would_write: false
```

이 순서가 좋은 이유는 WOM의 기존 원칙과 맞기 때문이다.

```text
preview first
human review
approve explicitly
provider call is separate
receipt is durable
```
