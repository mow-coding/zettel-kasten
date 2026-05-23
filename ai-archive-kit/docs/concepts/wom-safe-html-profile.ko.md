# WOM Safe HTML Profile

상태: 공개 설계 기준선
날짜: 2026-05-23

이 문서는 `zet`의 장기 문서 형식 방향을 기록합니다.

핵심 연속성: zet is always text.

## 명칭 경계

다음 표기는 반드시 구분합니다.

```text
WOM
  전체 open infrastructure, worldview, reference implementation family.

zet
  zettel-kasten에서 민팅되는 단위 문서.

ZET
  zets를 바탕으로 메신저, feed/SNS, 협업툴이 될 수 있는 zettel-kasten 기반 통신 계층.
```

`zet`는 기본 단위이므로 소문자로 씁니다.

`ZET`는 zets를 움직이는 통신 방식, 서비스, 프로토콜 계층을 가리키므로 대문자로 씁니다.

## 왜 HTML을 다시 검토하는가

초기 v0.2 문서들은 `zet`를 Markdown-compatible text plus metadata로 보았습니다.

이 선택은 초기 구현에는 좋았습니다.

- Markdown은 쓰기 쉽습니다.
- Git diff가 읽기 쉽습니다.
- AI가 초안을 만들기 쉽습니다.
- arbitrary HTML보다 보안 위험이 낮습니다.

하지만 WOM은 단순 note app이 아닙니다.

WOM은 open infrastructure입니다. 사용자는 각자 자기 zettel-kasten과 ZET 기반 SaaS를 만들 수 있어야 합니다.

그러면 형식 문제가 달라집니다.

텍스트 중심의 local AI 대화에는 Markdown이 충분할 수 있습니다. 하지만 custom SaaS layer에는 더 풍부한 web-native surface가 필요할 수 있습니다.

- media viewer,
- image gallery,
- audio/video timeline,
- map,
- diagram,
- collaboration workspace,
- feed,
- embedded source preview,
- accessibility-aware semantic structure,
- governed interactive view.

HTML도 text이며, 웹의 native structured document format입니다. 따라서 장기 canonical/interchange/rendering target으로는 Markdown-only보다 HTML이 더 큰 그릇입니다.

## 핵심 결정

민팅할 때마다 사용자가 canonical format을 Markdown 또는 HTML 중에서 고르게 만들지 않습니다.

장기 모델은 다음입니다.

```text
authoring/import formats
  Markdown
  plain text
  safe HTML input
  external editor/provider exports

canonical/interchange/rendering target
  WOM Safe HTML Profile
```

즉:

```text
draft input
-> normalization
-> validation
-> canonical WOM Safe HTML zet
```

Markdown은 authoring과 import compatibility format으로 계속 중요합니다.

기존 Markdown zets는 v0.2 compatibility line에서 계속 유효합니다.

## 아무 HTML이 아니다

`WOM Safe HTML Profile`은 아무 웹페이지나 canonical zet가 된다는 뜻이 아닙니다.

이 profile은 다음 조건을 만족해야 합니다.

- security-conscious,
- semantic,
- AI-readable,
- human-readable,
- source-object-aware,
- deterministic enough to replay,
- compatible with Git review,
- suitable for custom SaaS extension.

untrusted HTML은 반드시 validation과 sanitization이 필요합니다. OWASP는 untrusted HTML을 allowlist, output encoding, robust sanitization 없이 안전하게 보지 않습니다. GitHub Flavored Markdown도 Markdown을 HTML로 변환한 뒤 보안과 일관성을 위해 추가 post-processing과 sanitization을 적용한다고 설명합니다.

참고 표준과 가이드:

- WHATWG HTML Living Standard: `https://html.spec.whatwg.org/`
- GitHub Flavored Markdown Spec: `https://github.github.com/gfm/`
- OWASP Cross Site Scripting Prevention Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html`
- OWASP DOM Clobbering Prevention Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/DOM_Clobbering_Prevention_Cheat_Sheet.html`

## 필요한 profile 속성

미래의 WOM Safe HTML zet는 다음을 정의해야 합니다.

- required semantic document structure,
- required metadata envelope location,
- allowed HTML elements and attributes,
- blocked elements and attributes,
- `object_id`, content hash, manifest ref를 통한 source object reference,
- AI를 위한 deterministic text extraction,
- deterministic source-reference extraction,
- accessibility requirements,
- link와 embedded media 보안 규칙,
- local/package-relative asset 규칙,
- Git-diff-friendly formatting,
- proof/receipt hashing compatibility.

## CSS와 JavaScript 경계

CSS와 JavaScript는 HTML이 Markdown보다 확장성 있는 이유이지만, 동시에 안전성과 replay 위험이 생기는 곳입니다.

근시일 원칙:

```text
canonical zet
  semantic content와 safe presentation hook을 보관한다.

view/SaaS layer
  더 풍부한 styling과 interactive behavior를 담당한다.
```

CSS는 제한된 profile 또는 안전한 class/style token을 통해서만 허용하는 방향이 좋습니다.

JavaScript는 canonical archive memory 안에 자유롭게 embed하지 않는 편이 좋습니다. interactive behavior는 보통 canonical zet를 소비하는 viewer, app, plugin, ZET SaaS layer에 있어야 합니다.

미래 버전에서 signed 또는 sandboxed interaction bundle을 정의할 수는 있지만, 안전 모델이 명확해지기 전에는 core archival text와 분리해야 합니다.

## Source Object References

WOM Safe HTML zet는 raw provider URL을 primary source identity로 삼으면 안 됩니다.

우선할 것:

```text
object_id
sha256 or content hash
manifest ref
source binding id
archive-relative ref
```

external URL은 reference로 citation할 수 있지만, provider location이 source object identity를 대체해서는 안 됩니다.

## Compatibility Path

v0.2 구현은 Markdown compatibility를 유지합니다.

권장 rollout:

```text
v0.2.14
  WOM Safe HTML Profile 방향 문서화

v0.2.15
  기존 v0.2 Markdown 호환 zet를 위한 read-only Safe HTML Profile
  validator dry-run 추가

later
  mint dry-run에서 canonical HTML preview 제공

future minor release
  WOM Safe HTML을 preferred canonical/interchange format으로 전환
```

이 문서로 인해 기존 private archive migration은 필요하지 않습니다.

## v0.2.15 Validator Dry-Run

`v0.2.15`는 위 rollout의 첫 구체 도구를 추가합니다. v0.2 Markdown 호환 zet가 미래의 WOM Safe HTML Profile 마이그레이션과 호환 가능한지 미리 검사하는 읽기 전용 CLI dry-run validator입니다.

```bash
python ai-archive-kit/cli/archive.py check-safe-html <archive-root> \
  --path inbox/<draft-zet>.md \
  --dry-run \
  --format json
```

이 validator는:

- draft zet 또는 canonical zet를 읽기만 합니다.
- 파일을 쓰지 않습니다.
- Markdown을 HTML로 변환하지 않습니다.
- mint 결과를 바꾸지 않습니다.
- 기존 zet를 마이그레이션하지 않습니다.

반환되는 JSON에는 `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, `source_reference_preview` 필드가 포함됩니다.

첫 validator의 차단 목록 (맥락과 무관하게 항상 차단):

- `<script>` element,
- `<iframe>` element,
- `<object>` element,
- `<embed>` element,
- 링크 내 `javascript:` URL,
- `onclick=`, `onload=` 등 `on*=` inline event handler attribute.

이 목록은 최소 안전 기준선입니다. WOM Safe HTML Profile의 전체 element/attribute allowlist는 아직 확정되지 않았으며, 이번 validator는 명백히 unsafe한 패턴만 표시합니다. 이후 패치에서 명시적 allowlist, Markdown-to-Safe-HTML preview, 더 풍부한 warning이 추가될 수 있습니다.
