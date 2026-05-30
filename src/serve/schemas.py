"""요청/응답 Pydantic 스키마. 응답 모양은 real 교체 후에도 유지되도록 실제 데이터 형태에 맞춤.

좌표는 전부 (lat, lng) WGS84. 시각은 KST ISO8601 문자열(`2026-05-30T12:30:00+09:00`).
ETA 의 잔여시간은 초(`*_sec`). `source` 필드로 데이터 출처를 표기(real 교체 추적).
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Source(str, Enum):
    """이 응답(또는 필드)이 어디서 왔는지. 프론트가 dummy/real 구분."""
    dummy = "dummy"            # 아직 스텁
    reference = "reference"    # 기준데이터 (모델 불필요)
    live = "live"              # BIS 실황 패스스루
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
    first_time: str | None = Field(None, description="첫차 HHMM", examples=["0530"])
    last_time: str | None = Field(None, description="막차 HHMM", examples=["2230"])


class StopInRoute(BaseModel):
    stop_ord: int = Field(..., description="노선 내 정류장 순번", examples=[1])
    stop_id: int
    stop_name: str
    lat: float
    lng: float


class RouteDetail(BaseModel):
    stdid: int
    brt_no: str
    stops: list[StopInRoute]
    polyline: list[LatLng] = Field(..., description="지도 표시용 경로 vtx(순서대로)")
    source: Source = Source.dummy


class StopSummary(BaseModel):
    stop_id: int
    stop_name: str
    lat: float
    lng: float
    routes: list[str] = Field(default_factory=list, description="경유 노선번호들")
    source: Source = Source.dummy


# ── 실황 (BIS 패스스루) ───────────────────────────────
class BusLive(BaseModel):
    bus_id: str = Field(..., description="차량 식별(번호판 4자리 등)", examples=["1503"])
    stdid: int
    brt_no: str
    lat: float
    lng: float
    stop_ord: int | None = Field(None, description="최근 통과 정류장 순번")
    updated_at: str
    source: Source = Source.live


class ArrivalItem(BaseModel):
    brt_no: str
    stdid: int
    bus_id: str | None = None
    stops_away: int = Field(..., description="이 정류장까지 남은 정류장 수(실황)")
    eta_sec: int | None = Field(None, description="도착까지 잔여 초. 2차 실시간추론 들어오면 채움")
    eta_source: Source = Field(Source.dummy, description="eta_sec 의 출처(live=BIS / live_eta=2차)")


class ArrivalBoard(BaseModel):
    stop_id: int
    stop_name: str | None = None
    arrivals: list[ArrivalItem]


# ── 추론 (1차 사전 / 2차 실시간) ──────────────────────
class StopEtaItem(BaseModel):
    brt_no: str
    stdid: int
    eta_iso: str = Field(..., description="이 정류장 도착 예상 시각(KST ISO)")


class StopEta(BaseModel):
    stop_id: int
    mode: Source = Field(..., description="pre_eta(1차) | live_eta(2차)")
    dummy: bool = Field(True, description="더미값 여부(모델 완성 시 false). 값은 의미있게 채우되 실제 예측 아님")
    items: list[StopEtaItem]


class BusStopEtaItem(BaseModel):
    stop_ord: int
    stop_name: str
    eta_iso: str


class BusEta(BaseModel):
    bus_id: str
    stdid: int
    mode: Source = Field(..., description="pre_eta(1차) | live_eta(2차)")
    dummy: bool = Field(True, description="더미값 여부(모델 완성 시 false)")
    stops: list[BusStopEtaItem]


# ── 날씨 ──────────────────────────────────────────────
class WeatherNow(BaseModel):
    lat: float
    lng: float
    observed_at: str
    temp_c: float | None = None
    precipitation_type: str | None = Field(None, description="없음/비/비눈/눈/소나기")
    rain_mm: float | None = None
    sky: str | None = Field(None, description="맑음/구름많음/흐림")
    source: Source = Source.dummy


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


class PlanOption(BaseModel):
    leave_by: str = Field(..., description="이 안을 위해 지금 떠나야 하는 시각(KST ISO)")
    arrival_eta: str = Field(..., description="예상 도착 시각")
    miss_probability: float = Field(..., ge=0, le=1, description="버스를 놓칠 확률(0~1)")
    legs: list[PlanLeg]


class PlanResponse(BaseModel):
    recommended: PlanOption
    alternatives: list[PlanOption] = Field(default_factory=list)
    advice: str = Field(..., description="행동 요약(예: '지금 출발하세요')")
    dummy: bool = Field(True, description="더미값 여부(에이전트 완성 시 false). 값은 의미있게 채움")
    source: Source = Source.dummy


class Health(BaseModel):
    status: str = "ok"
    service: str = "blog-serve"
    version: str
