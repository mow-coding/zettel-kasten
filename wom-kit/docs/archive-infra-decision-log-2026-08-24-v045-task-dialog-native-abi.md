# v0.4.5 Windows Task Dialog 네이티브 ABI 핫픽스

## Context

공개 v0.4.4 wheel의 깨끗한 Windows 설치본에서 Letter 138 기계 검증은
통과했지만 `TaskDialogIndirect`가 `E_INVALIDARG`를 반환해 사람 결정창이 뜨지
않았다. 쓰기·승인 claim·checkpoint·receipt는 모두 0건이었다.

## Decision

- 공개 태그를 다시 쓰지 않고 v0.4.5 핫픽스를 낸다.
- 호출 스레드에 Common Controls v6 activation context를 명시적으로 활성화한다.
- `CommCtrl.h`의 1-byte packing을 ctypes Task Dialog 구조체에 적용한다.
- 사람은 계속 작업 실행 또는 취소만 결정하며 기계 증거를 검산하지 않는다.
- 깨끗한 설치본의 실제 네이티브 창과 비공개 복구본 중단·재개·되돌리기까지
  성공해야 Letter 138 클라이언트 안내를 재개한다.

## Consequences

원래 v0.4.5 이후로 계획한 복구 릴리스는 한 버전씩 뒤로 이동한다. 실제 클라이언트 아카이브는
클라이언트가 직접 실행하거나 명시적으로 위임하기 전까지 변경하지 않는다.
