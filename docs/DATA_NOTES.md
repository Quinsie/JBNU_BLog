# DATA NOTES — 데이터 품질 기록

> 후처리/학습에서 **반드시 참고**할 데이터 신뢰성 이슈를 날짜·범위별로 기록.
> 오염/누락/노선개편 등 "이 데이터는 이래서 믿으면 안 된다"를 남긴다.

## 2026-05-26 — 사용 금지 (오염 가능)
- 이 날 BLog 수집기 셋업·스모크 테스트 중, **같은 머신/공인 IP에서 수집기 3개가 동시 가동**
  (yubin 132@5s, gaeun 446@5s, BLog 테스트 446@5s)되어 ITS 서버 throttle 발생.
- 결과: timeout / SERVER_DISCONNECTED / 연결오류 다발 → **버스 위치 데이터에 다량의 결측·지연**.
- 또한 정적 데이터 정비 이전 시간대라 수집 의미도 적음.
- **결론: 2026-05-26 raw(bus/traffic 등)는 학습/후처리에 사용하지 않는다.**
- 같은 날 yubin/gaeun 기존 수집기를 중단하고 BLog 수집기 단독 체제로 전환.

## 날씨 수집 상태 (2026-05-26 기준)
- 실황(getUltraSrtNcst)·초단기예보(getUltraSrtFcst)·단기예보(getVilageFcst): **정상**, 43격자 거의 전부 ok.
- 중기예보 longForecast(getMidLandFcst/getMidTa, MidFcstInfoService): **HTTP_403**.
  - 원인: 현재 KMA 키가 "중기예보 조회서비스" API 에 **미구독**. (data.go.kr 는 API별 활용신청이 따로)
  - 영향: 중기(3~10일)는 버스 ETA 에 거의 무관 → 비차단. 필요 시 data.go.kr 에서 해당 서비스 활용신청하면 코드 수정 없이 자동 수집됨.

## 정적 데이터 기준
- stdid 총 **446개** (2026-05-26 API 기준). 작년(2025) 451 에서 노선 개편으로 -5.
- 정적 원본은 `data/reference/source/` (fetch 시각은 각 파일 `fetched_at`).
