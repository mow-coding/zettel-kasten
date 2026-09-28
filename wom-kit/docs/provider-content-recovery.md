# 공급자 본문·첨부 보존과 검색

이 경로는 공급자에서 받은 자료를 임시 폴더에 내려받는 데서 끝내지 않는다.
기존 source-intake, objet capture, derived-text, 검색 명령의 승인과 검증을
차례로 사용한다. 원본 bytes, 부모 자료와 첨부 관계, 검색 가능한 파생 본문을
각각 확인하고 마지막 영수증을 `receipts/provider-content/`에 남긴다.

현재 검증은 아직 공개되지 않은 개발 코드에서 합성 계정·응답·자료를 사용하는 시험이다.
합성 PAT를 실제 Windows 자격 증명 저장소에 보관하고 새 프로세스 두 개가 회수해
본문·첨부 보존 및 검색까지 완료하는 경로도 확인했다. 시험 항목은 정확히 삭제했다.
입력창·승인창은 모의 처리했으며 설치 배포본, 실제 공급자 연결, 실제 화면과
고객 수용은 별도 검증 대상이다.
임시 수집 성공이나 아래 명령의 존재만으로 해당 요청 전체가 완료된 것은 아니다.

## Notion: 저장된 PAT 사용

기존 보안 입력과 OS 저장소에 등록한 PAT를 사용한다. 일반 명령 인자에 토큰을
넣지 않는다. 공용 OAuth 앱·인증 서버는 현재 범위에서 제외되어 있고 필요하지 않다.
기존 `notion-page-recovery-request-build`가 만든 검토 요청에 미디어/연결 옵션을 붙인다.
아래 경로와 이름은 합성 예시다.

```text
archive notion-page-recovery-plan <archive-root> --request profiles/local/notion-page-recovery/synthetic.json --include-media --include-connections --dry-run
archive notion-page-recovery <archive-root> --request profiles/local/notion-page-recovery/synthetic.json --include-media --include-connections --approve --reviewed-by person:me --expected-plan-sha256 <reviewed-digest>
```

한 계획에 본문과 추가 수집 범위를 함께 결속한다. 본문 회수가 실패하면 첨부
수집을 시작하지 않는다. 별도 작업 프로세스가 저장된 PAT를 회수하며 각 요청의
승인 범위와 만료를 검사한다. 본문 쓰기 권한은 부여하지 않는다.

- 페이지·하위 블록의 파일을 정확한 bytes로 보존하고 원본 페이지 objet에 연결한다.
- 임시 파일 URL이 만료되면 소유 블록을 다시 읽어 URL을 한 번 갱신한다.
- 다운로드는 PAT를 전달하지 않으며, HTTPS 및 공개 주소를 매 요청·리다이렉트마다 검사한다.
- 관계 속성, 동기화 블록 참조, 데이터베이스 뷰 결과, 내부 링크, 페이지 멘션,
  댓글 맥락의 6종 연결 근거를 별도 원본으로 보존한다.
- Notion 뷰는 공식 목록·조회 및 같은 query 세대의 페이지를 사용한다.
  POST/DELETE는 읽기 결과 캐시의 생성·정리로 한정되며 페이지·블록을 수정하지 않는다.

공식 동작은 [Notion 뷰 API 안내](https://developers.notion.com/guides/data-apis/working-with-views)를 따른다.
연결에 페이지가 공유되지 않았거나 필요한 공급자 권한이 없으면 성공으로
판정하지 않는다. 페이지·뷰·댓글 권한과 오류의 실제 계정 검증이 필요하다.

## 연결 근거와 의미 관계를 구분

`connection-evidence-import`는 JSON/HTML/Markdown/관계 열을 지정한 CSV 또는
위 명령의 `connection_evidence_path`를 받는다. 원본의 hash와 위치를 유지한다.
CSV 관계 열은 `--relation-column "Related=property-id"`처럼 이름과 속성 ID를
명시하며 여러 열은 이 인자를 반복한다. 단순 텍스트 열을 임의로 관계로 해석하지 않는다.
AI가 실제로 검토한 판단과 페이지→zet 결속을 `--judgments`, `--bindings`로 받으며,
명령이 AI 모델을 호출했다고 표시하지 않는다. 파일 작성은 기존 AI 실행자가 맡을
수 있어 사용자가 연결 근거를 손으로 조립할 필요는 없다.

```text
archive connection-evidence-import <archive-root> --source <private-source-path> --source-page-id <page-id> --source-format json --batch-id synthetic --judgments <reviewed-judgments-path> --bindings <reviewed-bindings-path> --dry-run
```

승인 실행에는 같은 인자에 `--approve --reviewed-by person:me
--expected-plan-sha256 <reviewed-digest>`를 사용한다. 기계적 연결 종류, 의미,
엄격한 제텔카스텐 판단의 세 관점과 모델 실행 근거가 갖춰진 판단만 기존
zettel-edge-batch로 쓴다. 같은 의미 관계를 지지하는 여러 원본은 관계를 중복
작성하지 않고 모든 근거를 유지한다. 미검토·불일치 후보는 pending으로 남는다.

## IMAP: 증분 수집 후 본문과 첨부 보존

기존 `imap-mailbox-message-fetch`에 `--sync --extract-mime`를 붙이면 승인된
메일 수집 다음에 canonical 보존과 검색까지 이어진다. `--resume`는 같은
실행에서 실패한 UID를 이어받는다. 모든 메일 읽기는 읽기 전용 사서함과
BODY.PEEK를 사용한다.

UIDVALIDITY와 UID를 함께 기록하며 성공한 항목만 완료로 기록한다. 일부 UID가
실패해도 뒤의 성공 UID 때문에 누락되지 않는다. UIDVALIDITY가 바뀌면 새 세대로
읽고, 같은 bytes만 중복 제거한다. Message-ID만으로 서로 다른 메일을 합치지 않는다.
정확한 EML, 파생 본문, MIME 첨부·인라인 파일 및 부모 연결을 보존한다.
수집 후 canonical 단계에서 중단되어도 기존 intake 완료 영수증의 서명과
현재 bytes가 모두 맞으면 이를 재사용한다. 파일 존재만으로 완료 처리하지 않는다.

`collection_complete`, `capture_completed`, `search_verified`는 별도 결과다.
본문 검색 성공은 첨부 이미지 OCR이나 PDF 본문 추출 성공을 뜻하지 않는다.

## Tiro: 원본·공식 음원·파생 내용 분리

`tiro-content-import`는 기존 lossless bundle을 그대로 보존한다. 공식적으로
내보낸 로컬 음원은 note GUID와 확인한 SHA-256을 담은 비공개 audio manifest로
연결한다. 확인되지 않은 오디오 API 주소를 만들거나 사적 폴더를 찾아다니지 않는다.

```text
archive tiro-content-import <archive-root> --bundle <private-bundle-path> --audio-manifest <private-audio-list-path> --enrichment-manifest <private-ai-results-path> --batch-id synthetic --dry-run
```

AI 결과가 있으면 원본 bundle hash, note GUID, 실제 모델 실행 근거와 함께
별도 파생 자료로 보존한다. `ai_model_called: false`는 이 반입 명령 자체가 모델을
호출하지 않았다는 뜻이다. 음원이 제공되지 않은 노트는 `audio_unconfirmed`이며,
Tiro가 음원을 지원하지 않는다고 단정하지 않는다.

## 승인과 검증 경계

각 단계는 기존 승인 broker와 영수증을 그대로 사용한다. 유효한 전체 허용
세션은 추가 승인창 없이 실행하고, 일반 승인에서는 실제 작업 범위를 확인한다.
수집 실패, 본문 실패, 연결 판단 대기, canonical 실패를 전체 성공으로 바꾸지 않는다.
하위 capture가 실패하면 원래 `capture_result`와 `recovery`를 보존하며,
나중 단계에서 예외가 발생해도 이미 저장된 자료의 영수증과 `partial_or_unknown`
상태를 남긴다. 재실행 안내가 이전 실패의 복구 근거를 덮어쓰지 않는다.

`object_search_count`는 원본/첨부 objet 식별자가 실제 검색에 나타난 수이며,
`search_text_count`는 실제 등록하고 검색한 파생 본문의 수다. 첨부 자체의 bytes
검증과 부모 결속도 별도로 확인한다. 마지막 영수증은 앞 단계 영수증의 hash를
보존한다. 실패 뒤의 재실행·복구는 기존 준비/승인 근거와 현재 자료를 확인해야 한다.
