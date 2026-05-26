# ZET Publication Surface Example

상태: sanitized example
날짜: 2026-05-26

이 폴더는 데스크톱 AI 런타임에서 정리한 글을 WordPress 같은 외부 surface에 게시하는 흐름을 `ZET` UI 프로토타입으로 설명하기 위한 예시다.

포함된 파일:

```text
zet-publication-envelope.example.json
  canonical/draft zet와 외부 projection을 연결하는 data envelope 예시.

wordpress-post.safe-html.example.html
  외부 surface에 렌더링될 수 있는 안전한 HTML 본문 예시.

wordpress-title.example.txt
  외부 surface에 표시할 제목 예시.

wordpress-publish.example.ps1
  WordPress.com REST API 게시 helper의 sanitized 예시.
```

이 예시는 실제 사용자의 개인 아카이브, 실제 WordPress 사이트, 실제 토큰, 실제 AI 대화 원문, 로컬 파일 경로를 포함하지 않는다.

## Live Template Source

이 예시는 `style_template` 개념도 포함한다.

사용자가 외부 surface에 여러 글을 게시할 때, 매번 글자 크기와 줄간격, 소제목 여백, 썸네일 규격을 다시 지정하는 것은 부담이다. 대신 이미 마음에 드는 게시글 하나를 template post로 지정하고, 새 projection을 만들 때 그 게시글의 현재 스타일을 먼저 읽어올 수 있다.

```text
template post
-> current style profile
-> new projection body
-> provider publish
```

이 template post는 canonical archive memory가 아니다. 특정 surface에서 읽기 좋게 보이기 위한 visual reference다.

실제 구현에서는 template post를 다시 읽은 시각과 template content hash를 projection envelope 또는 receipt에 남겨야 한다.

## UX 의도

사용자는 "AI와 대화한 내용을 보기 좋게 정리해서 내 아카이브 블로그에 올린다"고 느낀다.

시스템은 내부적으로 다음을 분리해야 한다.

```text
private archive memory
  archive 안에서 검토되고 민팅되는 canonical record.

publication surface
  WordPress, feed, workspace, message 같은 외부 표시 화면.

projection receipt
  어떤 canonical/draft record가 어떤 surface에 어떤 body hash로 게시되었는지 남기는 evidence.
```

## 권장 UI 순서

```text
1. AI conversation summary
2. Draft zet preview
3. Scope/redaction gate
4. Projection preview
5. Explicit publish approval
6. Projection receipt
```

이 흐름은 미래 `ZET`의 `mint -> delegate -> attest -> anchor` 모델로 확장될 수 있다.
