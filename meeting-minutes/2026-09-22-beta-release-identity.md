# 베타 초안 식별 재발과 생성 응답 사용

## 관찰

자동 Beta delivery 35617995194는 생성 wheel의 Windows 설치 검증을 통과했지만, 초안 생성 직후 목록에 초안이 없어 `created_draft_not_found`로 실패했다. 이전 조회 방식을 목록으로 바꾼 수정만으로 hosted 자동 배포 복구를 입증하지 못했다. v0.4.37 안정판 공개와 공개 설치 성공은 별개이며 그대로 유효하다.

## 교정

초안 생성 REST 응답의 숫자 release ID를 보존하고, 이후 업로드·다운로드·공개도 release/asset ID로 수행한다. 생성 후 태그나 목록으로 같은 초안을 다시 발견할 필요가 없다. 재개 영수증은 저장소·태그·ID를 대조하며 잘못된 응답, 다른 자산, 비베타, 불완전 공개를 성공으로 바꾸지 않는다. 기존 공개 자산은 교체하지 않는다. 이미 통과한 제품 검사는 반복하지 않으며 배포 도구 전용 검사 경로를 사용한다.

근거: [GitHub release REST API](https://docs.github.com/en/rest/releases/releases#create-a-release), [asset REST API](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset).

## 검증 경계

합성 테스트로 목록이 생성된 초안을 노출하지 않는 조건, 생성 응답 재사용, 재개 시 생성 생략, 잘못된 식별자 거부, 숫자 asset endpoint의 바이너리 보존을 확인한다. 실제 원격 자동 실행의 공개 및 새 설치 완료는 별도 확인한다. 진행 중 이전 후보 실행은 새로운 수정의 성공 증거가 아니다. 고객 실제 업데이트는 미확인이다.
