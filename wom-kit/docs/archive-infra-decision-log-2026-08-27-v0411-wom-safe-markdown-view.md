# v0.4.11 WOM-safe Markdown 표시 결정

## 맥락

한국어에서는 ASCII 물결표(`~`)를 `3~5`, `서울~부산`,
`v0.4.3~v0.4.7`처럼 범위를 나타내는 데 자주 쓴다. 그러나 GFM은 한
개 또는 두 개의 물결표로 감싼 텍스트를 삭선으로 해석할 수 있다. 닫히지
않은 `**`도 사람용 Markdown 화면에서 뒤 문맥을 의도하지 않은 강조로
보이게 할 수 있다. 기존 작성 안내만으로는 이미 존재하는 zet와 실수를
안전하게 보여 주지 못한다.

## 결정

- 정본 zet의 원문 바이트는 절대 고치지 않는다.
- 사람에게 보여 줄 때만 순수 함수로 `wom_safe_markdown` 표시용 사본을
  만든다.
- 코드 블록, 들여쓴 코드, 인라인 코드는 그대로 둔다.
- autolink, 일반 URL, 링크 목적지와 제목, raw HTML 블록과 HTML 속성도
  실제 Markdown 문법으로 성립할 때만 Markdown 텍스트가 아니므로 그대로
  둔다. 닫히지 않은 태그, escaped opener, bare `](` 같은 유사 문법은 일반
  텍스트로 처리한다.
- 사용자가 완결한 `~~삭선~~`과 `**굵게**`는 그대로 둔다.
- 그 밖의 단일 물결표, 짝이 없는 이중 물결표, 짝이 없는 `**`에는
  CommonMark 역슬래시 이스케이프를 넣는다.
- 결과에는 원문이나 경로를 복제하지 않는 처리 건수와 원문/표시본
  SHA-256만 붙인다.
- 이 단계는 렌더러나 HTML을 추가하지 않으며 provider와 파일시스템을
  호출하지 않는다.
- blockquote·목록 컨테이너가 끝나면 그 안의 닫히지 않은 fenced code도
  함께 끝난 것으로 처리하고, 문단을 이어 쓰는 4칸 들여쓰기 줄을 코드로
  오판하지 않는다.
- CommonMark의 물리 줄은 CR, LF, CRLF로만 나누고 U+2028/U+2029를 줄이나
  공백으로 넓혀 해석하지 않는다.
- 여러 줄 HTML 속성과 빈 줄 없는 여러 줄 링크 제목은 보존한다. 링크 참조
  정의는 문단 첫머리의 연속된 유효 정의만 보호하고, 일반 문단 중간의
  `[label]:` 모양을 정의로 오인하지 않는다.
- blockquote와 목록의 lazy paragraph continuation은 setext heading이나 새
  목록으로 성급히 끊지 않는다. 반대로 실제 새 block은 서로 다른 강조
  delimiter를 억지로 짝짓지 않는다.
- 역슬래시 escape parity는 한 번의 선형 순회로 계산한다.

## 표준 근거

- CommonMark 0.31.2 2.4: ASCII 문장부호는 역슬래시 이스케이프할 수
  있고, 코드 블록과 코드 스팬에서는 역슬래시 이스케이프가 작동하지
  않는다. <https://spec.commonmark.org/0.31.2/#backslash-escapes>
- GFM 0.29 6.5: 한 개 또는 두 개의 물결표로 감싼 텍스트가 삭선이 될
  수 있으며, 세 개 이상의 연속 물결표는 삭선을 만들지 않는다.
  <https://github.github.com/gfm/#strikethrough-extension->
- CommonMark/GFM 4.4 및 4.5: 들여쓴 코드와 fenced code의 내용은
  인라인 Markdown으로 해석하지 않는다.
  <https://spec.commonmark.org/0.31.2/#indented-code-blocks>
  <https://spec.commonmark.org/0.31.2/#fenced-code-blocks>

## 결과

정본은 증거로 그대로 보존되며, UI가 없는 v0.x 단계에서도 Markdown
표면에 안전한 사람용 사본을 전달할 수 있다. 표시본은 원문을 대체하거나
새 정본이 되지 않는다.
