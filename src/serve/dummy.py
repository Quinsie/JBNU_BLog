"""dummy 응답 생성기. real 교체 전까지 모든 엔드포인트가 형태가 맞는 가짜 데이터를 돌려준다.

원칙: 모양은 real 과 동일(프론트가 동일 코드로 파싱), 값만 가짜. 결정적(난수 없이 index 기반)
이라 테스트가 재현 가능. KST 시각만 실제 now 를 쓴다.
"""

from __future__ import annotations

from datetime import timedelta

from src.common.clock import now_kst, ts_iso
from . import schemas as S

# 전주 시청 근처 기준점(dummy 좌표 베이스)
_BASE_LAT, _BASE_LNG = 35.8242, 127.1480


def _iso_in(seconds: int) -> str:
    return ts_iso(now_kst() + timedelta(seconds=seconds))


def route_list() -> list[S.RouteSummary]:
    return [
        S.RouteSummary(stdid=305000392, brt_no="101", subid="C", direction="1",
                       start_name="전북대종점", end_name="이마트", first_time="0530", last_time="2230"),
        S.RouteSummary(stdid=305001153, brt_no="2", subid="A", direction="1",
                       start_name="평화동종점", end_name="송천동", first_time="0540", last_time="2250"),
    ]


def route_detail(stdid: int) -> S.RouteDetail:
    stops = [
        S.StopInRoute(stop_ord=i, stop_id=305000000 + i, stop_name=f"정류장{i}",
                      lat=_BASE_LAT + i * 0.002, lng=_BASE_LNG + i * 0.002)
        for i in range(1, 6)
    ]
    return S.RouteDetail(
        stdid=stdid, brt_no="101", stops=stops,
        polyline=[S.LatLng(lat=s.lat, lng=s.lng) for s in stops],
        source=S.Source.dummy,
    )


def stop_summary(stop_id: int) -> S.StopSummary:
    return S.StopSummary(stop_id=stop_id, stop_name="전북대종점",
                         lat=_BASE_LAT, lng=_BASE_LNG, routes=["101", "2", "3-1"],
                         source=S.Source.dummy)


def stop_search(q: str) -> list[S.StopSummary]:
    return [S.StopSummary(stop_id=305032481 + i, stop_name=f"{q}{i or ''}",
                          lat=_BASE_LAT + i * 0.003, lng=_BASE_LNG + i * 0.003,
                          routes=["101"], source=S.Source.dummy) for i in range(3)]


def stops_nearby(lat: float, lng: float, radius_m: int) -> list[S.StopSummary]:
    return [S.StopSummary(stop_id=305032481 + i, stop_name=f"인근정류장{i}",
                          lat=lat + i * 0.001, lng=lng + i * 0.001,
                          routes=["101", "2"], source=S.Source.dummy) for i in range(3)]


def buses(stdid: int | None) -> list[S.BusLive]:
    sd = stdid or 305000392
    return [S.BusLive(bus_id=f"150{i}", stdid=sd, brt_no="101",
                      lat=_BASE_LAT + i * 0.004, lng=_BASE_LNG + i * 0.004,
                      stop_ord=i + 1, updated_at=ts_iso(), source=S.Source.live)
            for i in range(3)]


def bus_one(bus_id: str) -> S.BusLive:
    return S.BusLive(bus_id=bus_id, stdid=305000392, brt_no="101",
                     lat=_BASE_LAT, lng=_BASE_LNG, stop_ord=5,
                     updated_at=ts_iso(), source=S.Source.live)


def arrivals(stop_id: int) -> S.ArrivalBoard:
    items = [S.ArrivalItem(brt_no=no, stdid=305000392 + i, bus_id=f"150{i}",
                           stops_away=2 + i, eta_sec=None, eta_source=S.Source.dummy)
             for i, no in enumerate(["101", "2", "3-1"])]
    return S.ArrivalBoard(stop_id=stop_id, stop_name="전북대종점", arrivals=items)


def stop_eta(stop_id: int, mode: S.Source) -> S.StopEta:
    items = [S.StopEtaItem(brt_no=no, stdid=305000392 + i, eta_iso=_iso_in(300 * (i + 1)))
             for i, no in enumerate(["101", "2"])]
    return S.StopEta(stop_id=stop_id, mode=mode, items=items)


def bus_eta(bus_id: str, mode: S.Source) -> S.BusEta:
    stops = [S.BusStopEtaItem(stop_ord=i, stop_name=f"정류장{i}", eta_iso=_iso_in(120 * i))
             for i in range(1, 6)]
    return S.BusEta(bus_id=bus_id, stdid=305000392, mode=mode, stops=stops)


def weather(lat: float, lng: float) -> S.WeatherResponse:
    now = S.WeatherNow(lat=lat, lng=lng, observed_at=ts_iso(), temp_c=22.4,
                       precipitation_type="없음", rain_mm=0.0, sky="구름많음",
                       source=S.Source.dummy)
    fc = [S.WeatherForecastItem(forecast_at=_iso_in(3600 * h), temp_c=22.0 - h * 0.5,
                                precipitation_type="없음", rain_mm=0.0, sky="구름많음")
          for h in range(1, 4)]
    return S.WeatherResponse(now=now, forecast=fc)


def plan(req: S.PlanRequest) -> S.PlanResponse:
    rec = S.PlanOption(
        leave_by=_iso_in(120),
        arrival_eta=req.target_arrival,
        miss_probability=0.12,
        legs=[
            S.PlanLeg(mode="walk", desc="승차 정류장까지 도보", from_name="현재위치",
                      to_name="전북대종점", start_iso=_iso_in(120), end_iso=_iso_in(420)),
            S.PlanLeg(mode="wait", desc="버스 대기", from_name="전북대종점",
                      start_iso=_iso_in(420), end_iso=_iso_in(540)),
            S.PlanLeg(mode="bus", desc="101번 탑승", brt_no="101", stdid=305000392,
                      from_name="전북대종점", to_name="이마트",
                      start_iso=_iso_in(540), end_iso=_iso_in(1740)),
            S.PlanLeg(mode="walk", desc="목적지까지 도보", from_name="이마트",
                      to_name="목적지", start_iso=_iso_in(1740), end_iso=_iso_in(1920)),
        ],
    )
    alt = S.PlanOption(
        leave_by=_iso_in(600), arrival_eta=req.target_arrival, miss_probability=0.04,
        legs=[S.PlanLeg(mode="bus", desc="2번 탑승(안전 대안)", brt_no="2", stdid=305001153)],
    )
    return S.PlanResponse(recommended=rec, alternatives=[alt],
                          advice="약 2분 뒤 출발하면 101번을 타고 목표시각 전에 도착합니다.",
                          source=S.Source.dummy)
