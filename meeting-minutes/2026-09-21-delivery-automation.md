# 운영 개선 실제 구현

사용자는 문서로 합의한 작업 방식 개선을 매번 다음으로 미루는 행동을 명시적으로 교정했다. AI가 계획 작성과 적용 완료를 혼동하게 설명한 것이 문제였다. 현재 작업에서 CI 분류, 자동 베타, 출시 분리, 증거, 접수 흐름을 구현하고 실제 실행 근거를 남긴다.

P1: 개발 문서 허용 목록만 짧은 CI로 분류한다. 실행 소스·설치 안내·런타임 지침·알 수 없는 경로·빈 변경·수동 검증은 전체 검사로 남는다. 필수 결과 집계는 정확한 lane의 기대 상태와 비교하며 실패·취소·누락을 의도한 생략으로 오인하지 않는다.

베타 준비 조사: 현재 updater는 안정판 전용 버전 정규식과 공급 잠금·공개 URL·영수증 패턴을 사용한다. GitHub prerelease workflow만 추가하면 갱신이 차단된다. 버전·갱신·채널·자산 검증을 함께 연결해야 하며, 이 관찰은 후속으로 미루는 이유가 아니라 이번 구현 범위다.

공식 근거: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow 및 https://docs.github.com/en/rest/releases/releases. 경로 필터로 workflow 전체를 생략하면 필수 검사가 pending에 남을 수 있어 workflow 내 분류와 결과 집계를 사용한다. prerelease와 make_latest=false를 사용해 안정판 채널을 보존할 계획이다. 자동화 토큰의 push는 후속 workflow를 자동 유발한다고 가정하지 않는다.

구현 후보: CI 분류·결과 JSON, 전체 tree와 최신 PR 검사 증거 대조, canonical beta 버전/공급 잠금/영수증, 순차 prerelease workflow, draft 및 익명 파일 검증/새 환경 설치, 공개 접수 폼. 아직 원격 적용 완료가 아니다.

검증: 분류 4개, 소스 증거 2개, 버전 계약 4개, 공개 전 증거 검사 1개 통과. 기존 runtime 40개 중 실패 0·기존 생략 2, update transaction 201개 중 실패 0·기존 생략 4. 실제 합성 wheel 전환 시험은 진행 중이며 성공으로 계산하지 않는다.
