"""앱-facing API (Phase 7).

계층(내부 용어 — docs 와 일치):
- 기준데이터(reference): 노선·정류장·polyline·시간표. 모델 불필요 → real 가능.
- 실황(live, passthrough): BIS 실시간 버스위치 그대로. 모델 불필요 → real 가능.
- 사전추론(pre-eta, 1차): 배차시각 기반 도착예상. 1차 모델 의존 → dummy.
- 실시간추론(live-eta, 2차): 실시간 위치 기반 도착예상. 2차 모델 의존 → dummy.
- plan(에이전트): 목표도착형 이동계획. 에이전트+ETA 의존 → dummy. (도보 OSRM 은 내부 모듈)
- weather: 수집 중인 날씨 → real.

기본은 dummy 로 전 엔드포인트를 띄우고(완전한 Swagger 계약 제공),
기능이 완성되는 계층부터 라우터 단위로 real 로 교체한다.
"""
