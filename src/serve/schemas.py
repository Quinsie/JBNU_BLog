"""요청/응답 Pydantic 스키마.

핵심 모델(정정): 예측의 단위는 **물리 차량(plate)** 이 아니라 **(stdid, 발차슬롯) = 한 배차(trip)** 다.
- 발차슬롯 = 시간표 HHMM (trip_reconstruct·1차 모델의 학습 단위와 동일 소스).
- 1차 사전추론 = "그 배차가 발차부터 각 정류장에 도착하는 clock-time".
- 실황 버스 위치는 **익명 점**(개별 차량 추적·plate 식별 안 함 — 운영상 불가).

좌표 (lat,lng) WGS84. 시각 KST ISO8601. 잔여시간 `*_sec`. 출처 플래그 `source`/`dummy`/`eta_source`.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Source(str, Enum):
    dummy = "dummy"            # 아직 스텁(값은 의미있게 채우되 실제 예측 아님)
    reference = "reference"    # 기준데이터 (모델 불필요)
    live = "live"              # 우리 raw 최신 스냅샷 패스스루
    pre_eta = "pre_eta"        # 1차 사전추론
    live_eta = "live_eta"      # 2차 실시간추론


class LatLng(BaseModel):
    lat: float = Field(..., examples=[35.8242])
    lng: float = Field(..., examples=[127.1480])


# ── 기준데이터 ────────────────────────────────────────
class RouteSummary(BaseModel):
    stdid: int = Field(..., description="노선 표준ID(방향·분선 단위)", examples=[305000392])
    brt_no: str = Field(..., description="노선번호", examples=["101"])
    subid: str | None = None
    direction: str | None = None
    start_name: str | None = None
    end_name: str | None = None
    first_time: str | None = Field(None, examples=["0530"])
    last_time: str | None = Field(None, examples=["2230"])


class StopInRoute(BaseModel):
    stop_ord: int = Field(..., description="노선 내 정류장 순번(STOP_ORD)", examples=[1])
    stop_id: int
    stop_name: str
    lat: float
    lng: float


class RouteDetail(BaseModel):
    stdid: int
    brt_no: str
    stops: list[StopInRoute]
    polyline: list[LatLng] = Field(..., description="지도 표시용 경로 vtx(순서대로)")
    source: Source = Source.reference


class StopSummary(BaseModel):
    stop_id: int
    stop_name: str
    lat: float
    lng: float
    routes: list[str] = Field(default_factory=list, description="경유 노선번호들")
    source: Source = Source.reference


class DepartureList(BaseModel):
    """노선의 시간표상 발차슬롯들(= 배차 단위). 추론 엔드포인트의 `depart` 키 소스."""
    stdid: int
    brt_no: str | None = None
    daytype: str = Field(..., description="평일 | 토 | 일+공휴일", examples=["평일"])
    departures: list[str] = Field(..., description="발차시각 HHMM 정렬", examples=[["0600", "0625", "0650"]])
    source: Source = Source.reference


# ── 실황 (익명 위치) ──────────────────────────────────
class LiveBus(BaseModel):
    """노선 위 버스의 현재 위치(익명). 개별 차량 추적용 식별자 없음(plate 비유일·운영불가)."""
    stdid: int
    brt_no: str
    lat: float | None = None
    lng: float | None = None
    stop_ord: int | None = Field(None, description="최근 통과 정류장 순번")
    updated_at: str
    source: Source = Source.live


class ArrivalItem(BaseModel):
    brt_no: str
    stdid: int
    stops_away: int = Field(..., description="이 정류장까지 남은 정류장 수(실황 위치 기반)")
    eta_sec: int | None = Field(None, description="도착까지 잔여 초. 2차 실시간추론 자리 — 현재 더미")
    eta_source: Source = Field(Source.dummy, description="eta_sec 출처(live_eta=2차 / dummy)")


class ArrivalBoard(BaseModel):
    stop_id: int
    stop_name: str | None = None
    arrivals: list[ArrivalItem]


# ── 추론 (1차 사전 / 2차 실시간) — 단위 (stdid, 발차) ──
class StopArrival(BaseModel):
    stop_ord: int
    stop_name: str
    arrival_iso: str = Field(..., description="이 배차가 이 정류장에 도착하는 예상 clock-time(KST)")


class DepartureEta(BaseModel):
    """#10: stdid 의 특정 발차가 노선 위 각 정류장에 언제 도착하는지."""
    stdid: int
    brt_no: str | None = None
    depart: str = Field(..., description="발차시각 HHMM", examples=["1410"])
    mode: Source = Field(..., description="pre_eta(1차, 시간표기반) | live_eta(2차, 실시간보정)")
    dummy: bool = Field(True, description="더미값 여부(모델 완성 시 false)")
    stops: list[StopArrival]


class StopBoardItem(BaseModel):
    brt_no: str
    stdid: int
    depart: str = Field(..., description="이 배차의 발차시각 HHMM")
    arrival_iso: str = Field(..., description="이 정류장 도착 예상 clock-time(KST)")


class StopBoardEta(BaseModel):
    """#9: 한 정류장에 다가오는 (노선,발차)들의 도착예상."""
    stop_id: int
    mode: Source = Field(..., description="pre_eta(1차) | live_eta(2차)")
    dummy: bool = Field(True, description="더미값 여부(모델 완성 시 false)")
    items: list[StopBoardItem]


# ── 날씨 ──────────────────────────────────────────────
class WeatherNow(BaseModel):
    lat: float
    lng: float
    observed_at: str
    temp_c: float | None = None
    precipitation_type: str | None = Field(None, description="없음/비/비눈/눈 등")
    rain_mm: float | None = None
    sky: str | None = Field(None, description="맑음/구름많음/흐림")
    source: Source = Source.reference


class WeatherForecastItem(BaseModel):
    forecast_at: str
    temp_c: float | None = None
    precipitation_type: str | None = None
    rain_mm: float | None = None
    sky: str | None = None


class WeatherResponse(BaseModel):
    now: WeatherNow
    forecast: list[WeatherForecastItem] = Field(default_factory=list, description="단기예보(시간별)")


# ── 에이전트 (plan) ───────────────────────────────────
class PlanRequest(BaseModel):
    origin: LatLng = Field(..., description="현재 위치(GPS)")
    destination: LatLng | None = Field(None, description="목적지 좌표(임의 지점)")
    destination_query: str | None = Field(None, description="목적지 주소/검색어(좌표 없을 때 geocoding)")
    target_arrival: str = Field(..., description="목표 도착 시각(KST ISO)", examples=["2026-05-30T14:00:00+09:00"])
    user_speed_mps: float | None = Field(None, description="보행 속도(m/s). 미지정 시 기본값", examples=[1.3])


class PlanLeg(BaseModel):
    mode: str = Field(..., description="walk | wait | bus")
    desc: str
    from_name: str | None = None
    to_name: str | None = None
    start_iso: str | None = None
    end_iso: str | None = None
    brt_no: str | None = Field(None, description="bus leg 의 노선번호")
    stdid: int | None = None
    depart: str | None = Field(None, description="bus leg 이 타는 배차의 발차시각 HHMM")


class PlanOption(BaseModel):
    leave_by: str = Field(..., description="이 안을 위해 지금 떠나야 하는 시각(KST ISO)")
    arrival_eta: str = Field(..., description="예상 도착 시각")
    miss_probability: float = Field(..., ge=0, le=1, description="버스를 놓칠 확률(0~1)")
    legs: list[PlanLeg]


class PlanResponse(BaseModel):
    recommended: PlanOption
    alternatives: list[PlanOption] = Field(default_factory=list)
    advice: str = Field(..., description="행동 요약(예: '지금 출발하세요')")
    dummy: bool = Field(True, description="더미값 여부(에이전트 완성 시 false)")
    source: Source = Source.dummy


class Health(BaseModel):
    status: str = "ok"
    service: str = "blog-serve"
    version: str
