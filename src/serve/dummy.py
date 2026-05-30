"""dummy 응답 생성기 — **아직 모델이 없는 계층**(사전/실시간추론·plan)용.

원칙(사용자 합의):
- "더미"임을 응답에 **명시**(`dummy: true` / `source: dummy` / `eta_source: dummy`).
- 그러나 값은 **쓰레기 대신 의미있어 보이게** — 가능한 한 real 기준데이터/실황에 grounding
  (실제 정류장·노선·버스로 구성하고, *예측 수치만* 그럴듯하게 fabricate). null 금지.
- 결정적(난수 없음). KST 시각만 실제 now 사용.

real 로 교체할 땐 이 모듈 대신 모델 추론을 호출하고 `dummy=false` 로 둔다.
"""

from __future__ import annotations

from datetime import timedelta

from src.common.clock import now_kst, ts_iso
from . import store
from . import schemas as S

_BASE_LAT, _BASE_LNG = 35.8242, 127.1480   # 전주시청 근처 (fallback 좌표)
_SEG_SEC = 90   # 더미 정류장간 소요(그럴듯한 평균)


def _iso_in(seconds: int) -> str:
    return ts_iso(now_kst() + timedelta(seconds=seconds))


def arrival_eta_sec(stops_away: int) -> int:
    """도착보드 잔여시간 더미(2차 모델 전까지). stops_away 비례 — 의미있는 추정값."""
    return max(stops_away, 0) * _SEG_SEC + 30


def stop_eta(stop_id: int, mode: S.Source) -> S.StopEta:
    """정류장에 각 노선이 언제 — real 경유노선으로 구성, 도착시각만 더미."""
    idx = store._build_stop_index().get(stop_id)
    serves = idx["serves"] if idx else []
    items: list[S.StopEtaItem] = []
    seen = set()
    for i, (stdid, _ord) in enumerate(serves):
        if stdid in seen:
            continue
        seen.add(stdid)
        brt = store._stdid_brt.get(stdid) or "?"
        items.append(S.StopEtaItem(brt_no=brt, stdid=stdid, eta_iso=_iso_in(180 + 240 * len(items))))
        if len(items) >= 6:
            break
    if not items:   # 인덱스에 없는 정류장 → fallback
        items = [S.StopEtaItem(brt_no=no, stdid=305000392 + i, eta_iso=_iso_in(180 + 240 * i))
                 for i, no in enumerate(["101", "2"])]
    return S.StopEta(stop_id=stop_id, mode=mode, dummy=True, items=items)


def bus_eta(bus_id: str, mode: S.Source) -> S.BusEta:
    """버스가 각 정류장에 언제 — real 버스의 real 노선 정류장으로 구성, 시각만 더미."""
    b = store.bus_one(bus_id)
    stdid = b["stdid"] if b else 305000392
    cur_ord = (b.get("stop_ord") or 0) if b else 0
    rd = store.route_detail(stdid)
    stops = rd["stops"] if rd else []
    ahead = [s for s in stops if s["stop_ord"] >= cur_ord] or stops
    items = [S.BusStopEtaItem(stop_ord=s["stop_ord"], stop_name=s["stop_name"],
                              eta_iso=_iso_in(_SEG_SEC * (k + 1)))
             for k, s in enumerate(ahead[:20])]
    if not items:
        items = [S.BusStopEtaItem(stop_ord=i, stop_name=f"정류장{i}", eta_iso=_iso_in(_SEG_SEC * i))
                 for i in range(1, 6)]
    return S.BusEta(bus_id=bus_id, stdid=stdid, mode=mode, dummy=True, stops=items)


def plan(req: S.PlanRequest) -> S.PlanResponse:
    """이동계획 더미 — 출발지 인근 real 정류장·real 노선으로 구성, 시각·확률만 fabricate."""
    near = store.stops_nearby(req.origin.lat, req.origin.lng, 1000, limit=1)
    if near:
        board = near[0]
        board_name = board["stop_name"]
        brt = (board["routes"] or ["101"])[0]
    else:
        board_name, brt = "전북대종점", "101"
    rec = S.PlanOption(
        leave_by=_iso_in(120), arrival_eta=req.target_arrival, miss_probability=0.12,
        legs=[
            S.PlanLeg(mode="walk", desc="승차 정류장까지 도보", from_name="현재위치",
                      to_name=board_name, start_iso=_iso_in(120), end_iso=_iso_in(420)),
            S.PlanLeg(mode="wait", desc="버스 대기", from_name=board_name,
                      start_iso=_iso_in(420), end_iso=_iso_in(540)),
            S.PlanLeg(mode="bus", desc=f"{brt}번 탑승", brt_no=brt,
                      from_name=board_name, to_name="하차정류장",
                      start_iso=_iso_in(540), end_iso=_iso_in(1740)),
            S.PlanLeg(mode="walk", desc="목적지까지 도보", from_name="하차정류장",
                      to_name="목적지", start_iso=_iso_in(1740), end_iso=_iso_in(1920)),
        ],
    )
    alt = S.PlanOption(
        leave_by=_iso_in(420), arrival_eta=req.target_arrival, miss_probability=0.04,
        legs=[S.PlanLeg(mode="bus", desc=f"{brt}번 대신 한 대 일찍(안전 대안)", brt_no=brt,
                        from_name=board_name, to_name="하차정류장",
                        start_iso=_iso_in(840), end_iso=_iso_in(2040))],
    )
    return S.PlanResponse(
        recommended=rec, alternatives=[alt], dummy=True, source=S.Source.dummy,
        advice=f"약 2분 뒤 출발하면 {board_name}에서 {brt}번을 타고 목표시각 전에 도착합니다.",
    )
